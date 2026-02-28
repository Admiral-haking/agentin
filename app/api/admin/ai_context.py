from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_session
from app.knowledge.store import get_store_knowledge_text
from app.models.app_log import AppLog
from app.models.conversation_state import ConversationState
from app.models.message import Message
from app.models.bot_settings import BotSettings
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.admin.behavior import AIContextOut
from app.schemas.admin.ai_context import AISimulateIn, AISimulateOut, AIPinProductIn
from app.schemas.webhook import NormalizedMessage
from app.services.context_bundle import build_context_bundle
from app.services.product_catalog import get_catalog_snapshot
from app.services.agent_trace import build_agent_trace_turns
from app.services.processor import (
    build_llm_messages,
    build_response_log_summary,
    get_recent_response_logs,
)
from app.services.user_behavior_store import build_behavior_snapshot, get_behavior_profile
from app.services.prompts import load_prompt
from app.services.campaigns import get_active_campaigns
from app.services.faqs import get_verified_faqs
from app.services.conversation_state import (
    build_state_payload,
    get_or_create_state,
    infer_category as infer_state_category,
    update_state,
)
from app.services.app_log_store import log_event
from app.services.product_matcher import match_products_with_scores
from app.services.llm_clients import LLMError, generate_reply
from app.services.llm_router import choose_provider
from app.services.guardrails import post_process, fallback_llm_text
from app.services.product_presenter import build_selected_product_payload
from app.models.product import Product

router = APIRouter(prefix="/admin/ai", tags=["admin"])


@router.get("/context", response_model=AIContextOut)
async def get_ai_context(
    conversation_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    external_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AIContextOut:
    user: User | None = None
    conversation: Conversation | None = None
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        user = await session.get(User, conversation.user_id)
    elif user_id is not None or external_id:
        if user_id is not None:
            user = await session.get(User, user_id)
        else:
            result = await session.execute(
                select(User).where(User.external_id == external_id)
            )
            user = result.scalars().first()
    else:
        raise HTTPException(status_code=400, detail="conversation_id or user_id/external_id is required")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    bot_settings = result.scalars().first()
    base_prompt = bot_settings.system_prompt if bot_settings else load_prompt("system.txt")
    store_knowledge = get_store_knowledge_text()

    catalog_snapshot = await get_catalog_snapshot(session)
    catalog_summary = catalog_snapshot.summary if catalog_snapshot else None

    if conversation is None:
        result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conversation = result.scalars().first()

    recent_messages: list[Message] = []
    if conversation:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(10)
        )
        recent_messages = list(reversed(result.scalars().all()))

    behavior_profile = await get_behavior_profile(session, user.id)
    behavior_snapshot = build_behavior_snapshot(
        behavior_profile,
        recent_messages[-1].content_text if recent_messages else None,
    )

    conversation_state = None
    if conversation:
        conversation_state = await session.get(ConversationState, conversation.id)
    conversation_state_payload = build_state_payload(conversation_state)

    response_log_summary = None
    if conversation:
        logs = await get_recent_response_logs(session, conversation.id, 5)
        response_log_summary = build_response_log_summary(logs)

    decision_events: list[dict[str, object]] = []
    if conversation:
        result = await session.execute(
            select(AppLog)
            .where(
                AppLog.event_type.in_(
                    {
                        "intent_detected",
                        "state_updated",
                        "slots_needed",
                        "product_matched",
                        "selected_product_locked",
                        "link_request_handled",
                        "reply_rewritten_by_guardrail",
                        "template_blocked",
                        "hallucination_prevented",
                        "loop_detected",
                    }
                )
            )
            .where(
                cast(AppLog.data["conversation_id"].astext, Integer)
                == conversation.id
            )
            .order_by(AppLog.created_at.desc())
            .limit(30)
        )
        decision_events = [
            {
                "event_type": log.event_type,
                "message": log.message,
                "data": log.data,
                "created_at": log.created_at.isoformat()
                if log.created_at
                else None,
            }
            for log in result.scalars().all()
        ]

    campaigns = await get_active_campaigns(session)
    faqs = await get_verified_faqs(session)

    bundle = build_context_bundle(
        base_prompt=base_prompt,
        store_text=store_knowledge,
        campaigns=campaigns,
        faqs=faqs,
        catalog_summary=catalog_summary,
        behavior_snapshot=behavior_snapshot,
        conversation_state=conversation_state_payload,
        recent_messages=recent_messages,
        user=user,
        admin_notes=bot_settings.admin_notes if bot_settings else None,
        response_log_summary=response_log_summary,
    )

    sections = dict(bundle.sections)
    sections["behavior_snapshot"] = behavior_snapshot
    sections["conversation_state_payload"] = conversation_state_payload
    sections["decision_events"] = decision_events
    sections["recent_messages_raw"] = [
        {
            "role": msg.role,
            "type": msg.type,
            "text": msg.content_text,
            "created_at": msg.created_at,
        }
        for msg in recent_messages
    ]

    return AIContextOut(
        user={"id": user.id, "external_id": user.external_id, "username": user.username},
        context=bundle.system_prompt,
        sections=sections,
    )


@router.get("/trace/{conversation_id}", response_model=dict)
async def get_agent_trace_by_conversation(
    conversation_id: int,
    limit_turns: int = Query(default=15, ge=1, le=60),
    log_limit: int = Query(default=800, ge=100, le=5000),
    include_debug_data: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user = await session.get(User, conversation.user_id)
    state = await session.get(ConversationState, conversation.id)
    state_payload = build_state_payload(state)

    message_limit = min(2500, max(300, limit_turns * 80))
    message_result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(message_limit)
    )
    messages = list(reversed(message_result.scalars().all()))

    log_result = await session.execute(
        select(AppLog)
        .where(cast(AppLog.data["conversation_id"].astext, Integer) == conversation.id)
        .order_by(AppLog.created_at.desc())
        .limit(log_limit)
    )
    logs = list(reversed(log_result.scalars().all()))
    turns = build_agent_trace_turns(
        logs=logs,
        messages=messages,
        limit_turns=limit_turns,
        include_debug_data=include_debug_data,
    )

    unresolved = False
    if (
        conversation.last_user_message_at is not None
        and (
            conversation.last_bot_message_at is None
            or conversation.last_bot_message_at < conversation.last_user_message_at
        )
    ):
        unresolved = True

    return {
        "conversation": {
            "id": conversation.id,
            "status": conversation.status,
            "user_id": conversation.user_id,
            "last_user_message_at": conversation.last_user_message_at.isoformat()
            if conversation.last_user_message_at
            else None,
            "last_bot_message_at": conversation.last_bot_message_at.isoformat()
            if conversation.last_bot_message_at
            else None,
        },
        "user": {
            "id": user.id if user else None,
            "external_id": user.external_id if user else None,
            "username": user.username if user else None,
        },
        "state": state_payload,
        "stats": {
            "turn_count": len(turns),
            "messages_loaded": len(messages),
            "logs_loaded": len(logs),
            "unresolved": unresolved,
        },
        "turns": turns,
    }


@router.post("/clear_state")
async def clear_state(
    conversation_id: int = Query(gt=0),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict[str, str]:
    state = await session.get(ConversationState, conversation_id)
    if state:
        await session.delete(state)
        await session.commit()
        await log_event(
            session,
            level="info",
            event_type="state_cleared",
            data={"conversation_id": conversation_id},
        )
    return {"status": "ok"}


@router.post("/simulate_reply", response_model=AISimulateOut)
async def simulate_reply(
    payload: AISimulateIn,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AISimulateOut:
    conversation = await session.get(Conversation, payload.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user = await session.get(User, conversation.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(12)
    )
    history = list(reversed(result.scalars().all()))

    message_text = payload.message
    if not message_text:
        for msg in reversed(history):
            if msg.role == "user" and msg.content_text:
                message_text = msg.content_text
                break
    if not message_text:
        message_text = "سلام"

    normalized = NormalizedMessage(
        sender_id=user.external_id or "0",
        receiver_id=None,
        message_type="text",
        text=message_text,
        raw_payload={},
    )

    bot_settings = None
    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    bot_settings = result.scalars().first()

    campaigns = await get_active_campaigns(session)
    faqs = await get_verified_faqs(session)
    catalog_snapshot = await get_catalog_snapshot(session)
    catalog_summary = catalog_snapshot.summary if catalog_snapshot else None

    behavior_profile = await get_behavior_profile(session, user.id)
    behavior_snapshot = build_behavior_snapshot(
        behavior_profile,
        message_text,
    )

    conversation_state = await session.get(ConversationState, conversation.id)
    conversation_state_payload = build_state_payload(conversation_state)

    matches = await match_products_with_scores(session, message_text, limit=8)
    products = [match.product for match in matches]

    llm_messages = build_llm_messages(
        history=history,
        bot_settings=bot_settings,
        message=normalized,
        user=user,
        products=products,
        campaigns=campaigns,
        faqs=faqs,
        catalog_summary=catalog_summary,
        behavior_snapshot=behavior_snapshot,
        conversation_state=conversation_state_payload,
    )

    provider = choose_provider(normalized, bot_settings.ai_mode if bot_settings else None)
    try:
        reply_text, usage = await generate_reply(provider, llm_messages)
    except LLMError:
        reply_text = fallback_llm_text()
        usage = {}

    max_chars = (
        bot_settings.max_output_chars
        if bot_settings and bot_settings.max_output_chars
        else None
    )
    reply_text = post_process(reply_text, max_chars=max_chars, fallback_text=fallback_llm_text())

    sources = {
        "campaigns": len(campaigns),
        "faqs": len(faqs),
        "products": len(products),
        "catalog_summary": bool(catalog_summary),
    }
    return AISimulateOut(
        draft_reply=reply_text,
        context_used={
            "system_prompt": llm_messages[0]["content"] if llm_messages else "",
            "message": message_text,
        },
        sources=sources,
    )


@router.post("/pin_selected_product")
async def pin_selected_product(
    payload: AIPinProductIn,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict[str, object]:
    conversation = await session.get(Conversation, payload.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    product = await session.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    state = await get_or_create_state(session, conversation.id)
    selected_payload = build_selected_product_payload(product)
    await update_state(
        session,
        conversation.id,
        intent=state.intent or "product_selected",
        category=state.category or infer_state_category(product.title or product.slug or ""),
        slots_required=state.slots_required,
        slots_filled=state.slots_filled,
        last_user_question=state.last_user_question,
        state=state,
        selected_product=selected_payload,
        preserve_selected_product=False,
        last_handler_used="admin_pin",
    )
    await log_event(
        session,
        level="info",
        event_type="selected_product_locked",
        data={
            "conversation_id": conversation.id,
            "product_id": product.id,
            "source": "admin_pin",
        },
    )
    return {"status": "ok", "product_id": product.id}
