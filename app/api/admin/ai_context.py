from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_session
from app.knowledge.store import get_store_knowledge_text
from app.models.conversation_state import ConversationState
from app.models.message import Message
from app.models.bot_settings import BotSettings
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.admin.behavior import AIContextOut
from app.schemas.admin.ai_context import AISimulateIn, AISimulateOut
from app.schemas.webhook import NormalizedMessage
from app.services.context_bundle import build_context_bundle
from app.services.product_catalog import get_catalog_snapshot
from app.services.processor import (
    build_llm_messages,
    build_response_log_summary,
    get_recent_response_logs,
)
from app.services.user_behavior_store import build_behavior_snapshot, get_behavior_profile
from app.services.prompts import load_prompt
from app.services.campaigns import get_active_campaigns
from app.services.faqs import get_verified_faqs
from app.services.conversation_state import build_state_payload
from app.services.product_matcher import match_products_with_scores
from app.services.llm_clients import LLMError, generate_reply
from app.services.llm_router import choose_provider
from app.services.guardrails import post_process, fallback_llm_text

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
