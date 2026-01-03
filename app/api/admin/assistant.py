from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse
import csv
import io
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import get_request_ip, require_role
from app.core.config import settings
from app.core.database import get_session
from app.models import (
    AppLog,
    AssistantAction,
    AssistantConversation,
    AssistantMessage,
    BotSettings,
    Campaign,
    Conversation,
    Faq,
    Message,
    Product,
    User,
)
from app.schemas.admin.assistant import (
    AssistantActionCreate,
    AssistantActionOut,
    AssistantActionUpdate,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantConversationCreate,
    AssistantConversationOut,
    AssistantConversationUpdate,
    AssistantMessageOut,
)
from app.schemas.admin.campaign import CampaignCreate, CampaignOut, CampaignUpdate
from app.schemas.admin.faq import FaqCreate, FaqOut, FaqUpdate
from app.schemas.admin.product import ProductCreate, ProductOut, ProductUpdate
from app.schemas.admin.settings import BotSettingsOut, BotSettingsUpdate
from app.schemas.webhook import NormalizedMessage
from app.services.audit import record_audit
from app.services.llm_clients import LLMError, generate_reply
from app.services.llm_router import choose_provider
from app.services.product_matcher import match_products
from app.services.processor import generate_with_fallback, record_usage
from app.services.prompts import load_prompt
from app.utils.time import utc_now

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/assistant", tags=["admin"])

DEFAULT_ASSISTANT_PROMPT = (
    "You are an operations copilot for the Instagram DM bot admin team.\n"
    "Respond in the same language as the user's message.\n"
    "Be concise, actionable, and clear. Use bullet steps when listing tasks.\n"
    "If a request is ambiguous, ask one short clarifying question.\n"
    "Never invent credentials, tokens, or secrets. If asked, explain how to obtain or store them securely.\n"
    "Warn before destructive actions and prefer safe, reversible steps."
)

ALLOWED_ACTION_TYPES = {
    "settings.update",
    "faq.create",
    "faq.update",
    "faq.delete",
    "campaign.create",
    "campaign.update",
    "campaign.delete",
    "product.create",
    "product.update",
    "product.delete",
}

EXPORT_TYPES = {"messages", "actions", "conversations", "training"}


async def _get_active_settings(session: AsyncSession) -> BotSettings | None:
    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    return result.scalars().first()


async def _get_or_create_settings(session: AsyncSession) -> BotSettings:
    settings_record = await _get_active_settings(session)
    if settings_record:
        return settings_record

    system_prompt = load_prompt("system.txt")
    settings_record = BotSettings(
        ai_mode=settings.LLM_MODE,
        system_prompt=system_prompt,
        max_history_messages=settings.MAX_HISTORY_MESSAGES,
        max_output_chars=settings.MAX_RESPONSE_CHARS,
        language=settings.DEFAULT_LANGUAGE,
        active=True,
    )
    session.add(settings_record)
    await session.commit()
    return settings_record


def _sanitize_messages(
    messages: list[dict[str, str]],
    max_history: int,
) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for message in messages:
        content = message["content"].strip()
        if not content:
            continue
        cleaned.append({"role": message["role"], "content": content})

    if max_history > 0 and len(cleaned) > max_history:
        cleaned = cleaned[-max_history:]
    if settings.LLM_MAX_USER_TURNS > 0:
        trimmed: list[dict[str, str]] = []
        user_turns = 0
        for msg in reversed(cleaned):
            trimmed.append(msg)
            if msg.get("role") == "user":
                user_turns += 1
                if user_turns >= settings.LLM_MAX_USER_TURNS:
                    break
        trimmed.reverse()
        cleaned = trimmed
    return cleaned


def _build_product_context(products: list[Product]) -> str:
    lines: list[str] = []
    for product in products:
        title = product.title or product.slug or "بدون عنوان"
        price = str(product.price) if product.price is not None else "نامشخص"
        old_price = str(product.old_price) if product.old_price is not None else None
        availability = (
            product.availability.value
            if hasattr(product.availability, "value")
            else str(product.availability)
        )
        parts = [title, f"قیمت: {price}"]
        if old_price:
            parts.append(f"قبل: {old_price}")
        parts.append(f"موجودی: {availability}")
        if product.product_id:
            parts.append(f"مدل: {product.product_id}")
        if product.page_url:
            parts.append(f"لینک: {product.page_url}")
        lines.append(" | ".join(parts))
    return (
        "[PRODUCTS]\n"
        + "\n".join(f"- {line}" for line in lines)
        + "\nRules:\n"
        "- فقط از قیمت‌های بالا استفاده کن و قیمت جدید نساز.\n"
        "- اگر قیمت نامشخص بود، همین را اعلام کن."
    )


def _build_product_url_from_slug(slug: str) -> str | None:
    slug_value = slug.strip().strip("/")
    if not slug_value:
        return None
    base = settings.SITEMAP_URL or settings.TOROB_PRODUCTS_URL
    if not base:
        return None
    parsed = urlparse(base)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/product/{slug_value}"


async def _prepare_product_action_payload(
    session: AsyncSession,
    action_type: str,
    payload_data: dict,
) -> dict:
    if action_type == "product.create" and not payload_data.get("page_url"):
        slug = payload_data.get("slug")
        if isinstance(slug, str):
            page_url = _build_product_url_from_slug(slug)
            if page_url:
                payload_data["page_url"] = page_url

    if action_type in {"product.update", "product.delete"} and not payload_data.get("id"):
        product_id = payload_data.get("product_id")
        page_url = payload_data.get("page_url")
        slug = payload_data.get("slug")
        query = select(Product.id)
        if product_id:
            query = query.where(Product.product_id == str(product_id))
        elif page_url:
            query = query.where(Product.page_url == str(page_url))
        elif slug:
            query = query.where(Product.slug == str(slug))
        else:
            return payload_data

        result = await session.execute(query)
        ids = list(result.scalars().all())
        if len(ids) == 1:
            payload_data["id"] = ids[0]
        elif len(ids) > 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple products match this slug. Provide id or page_url.",
            )
    return payload_data


async def _require_conversation(
    session: AsyncSession,
    conversation_id: int,
    admin_id: int,
    is_admin: bool,
) -> AssistantConversation:
    conversation = await session.get(AssistantConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not is_admin and conversation.admin_id != admin_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return conversation


async def _build_snapshot(session: AsyncSession) -> str:
    user_count = await session.scalar(select(func.count(User.id)))
    conversation_count = await session.scalar(select(func.count(Conversation.id)))
    message_count = await session.scalar(select(func.count(Message.id)))
    faq_count = await session.scalar(select(func.count(Faq.id)))
    campaign_count = await session.scalar(select(func.count(Campaign.id)))
    product_count = await session.scalar(select(func.count(Product.id)))
    active_settings = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.updated_at.desc())
        .limit(1)
    )
    settings_record = active_settings.scalars().first()
    pending_actions = await session.scalar(
        select(func.count(AssistantAction.id)).where(AssistantAction.status == "pending")
    )

    recent_users = await session.execute(
        select(User).order_by(User.updated_at.desc()).limit(5)
    )
    recent_errors = await session.execute(
        select(AppLog)
        .where(AppLog.level.in_(["warning", "error"]))
        .order_by(AppLog.created_at.desc())
        .limit(3)
    )
    recent_conversations = await session.execute(
        select(Conversation, User)
        .join(User, Conversation.user_id == User.id)
        .order_by(Conversation.updated_at.desc())
        .limit(10)
    )
    recent_messages = await session.execute(
        select(Message, Conversation, User)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
        .order_by(Message.created_at.desc())
        .limit(80)
    )

    lines = [
        "System snapshot:",
        f"- Users: {user_count or 0}",
        f"- Conversations: {conversation_count or 0}",
        f"- Messages: {message_count or 0}",
        f"- FAQs: {faq_count or 0}",
        f"- Campaigns: {campaign_count or 0}",
        f"- Products: {product_count or 0}",
        f"- Pending approvals: {pending_actions or 0}",
    ]
    if settings_record:
        lines.append(
            "- Active AI mode: {mode} | max_output: {max_output} | history: {history}".format(
                mode=settings_record.ai_mode,
                max_output=settings_record.max_output_chars,
                history=settings_record.max_history_messages,
            )
        )

    recent_user_items = []
    for user in recent_users.scalars().all():
        label = user.username or "unknown"
        recent_user_items.append(f"{label} ({user.external_id})")
    if recent_user_items:
        lines.append(f"- Recent contacts: {', '.join(recent_user_items)}")

    error_items = []
    for log in recent_errors.scalars().all():
        detail = log.message or log.event_type or "unknown"
        error_items.append(detail[:120])
    if error_items:
        lines.append(f"- Recent warnings: {', '.join(error_items)}")

    conversation_items = []
    for conversation, user in recent_conversations.all():
        last_user = (
            conversation.last_user_message_at.isoformat()
            if conversation.last_user_message_at
            else "-"
        )
        last_bot = (
            conversation.last_bot_message_at.isoformat()
            if conversation.last_bot_message_at
            else "-"
        )
        label = user.username or "unknown"
        conversation_items.append(
            f"conv#{conversation.id} user={label} ({user.external_id}) status={conversation.status} "
            f"last_user={last_user} last_bot={last_bot}"
        )
    if conversation_items:
        lines.append("Recent conversations:")
        lines.extend([f"- {item}" for item in conversation_items])

    message_items = []
    for message, conversation, user in recent_messages.all():
        label = user.username or "unknown"
        content = (message.content_text or "").replace("\n", " ").strip()
        if not content and message.media_url:
            content = message.media_url.strip()
        if len(content) > 220:
            content = f"{content[:220]}..."
        payload_preview = ""
        if message.payload_json:
            payload_preview = json.dumps(message.payload_json, ensure_ascii=False)
            if len(payload_preview) > 220:
                payload_preview = f"{payload_preview[:220]}..."
        timestamp = (
            message.created_at.isoformat() if message.created_at else ""
        )
        message_items.append(
            "msg#{id} conv#{conv} user={user} ({ext}) role={role} type={typ} "
            "time={time} text=\"{text}\" payload={payload}".format(
                id=message.id,
                conv=conversation.id,
                user=label,
                ext=user.external_id,
                role=message.role,
                typ=message.type,
                time=timestamp,
                text=content,
                payload=payload_preview or "{}",
            )
        )
    if message_items:
        lines.append("Recent messages:")
        lines.extend([f"- {item}" for item in message_items])

    return "\n".join(lines)


async def _get_export_conversations(
    session: AsyncSession,
    admin,
    conversation_id: int | None,
    since: datetime | None,
) -> list[AssistantConversation]:
    query = select(AssistantConversation)
    if conversation_id:
        query = query.where(AssistantConversation.id == conversation_id)
    if admin.role != "admin":
        query = query.where(AssistantConversation.admin_id == admin.id)
    if since:
        query = query.where(AssistantConversation.created_at >= since)
    result = await session.execute(query.order_by(AssistantConversation.created_at.asc()))
    return list(result.scalars().all())


async def _execute_action(
    session: AsyncSession,
    action: AssistantAction,
    admin_id: int,
    request: Request,
) -> dict[str, Any]:
    payload = action.payload_json or {}
    ip = await get_request_ip(request)
    user_agent = request.headers.get("user-agent")

    if action.action_type == "settings.update":
        settings_record = await _get_or_create_settings(session)
        before = BotSettingsOut.model_validate(settings_record)
        update_data = BotSettingsUpdate(**payload).model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No settings changes provided")
        for key, value in update_data.items():
            setattr(settings_record, key, value)
        await session.commit()
        await record_audit(
            session,
            admin_id=admin_id,
            entity="settings",
            action="update",
            before=before,
            after=settings_record,
            ip=ip,
            user_agent=user_agent,
        )
        return {"settings_id": settings_record.id, "updated": list(update_data.keys())}

    if action.action_type.startswith("faq."):
        if action.action_type == "faq.create":
            data = FaqCreate(**payload).model_dump()
            record = Faq(**data)
            session.add(record)
            await session.commit()
            await record_audit(
                session,
                admin_id=admin_id,
                entity="faq",
                action="create",
                before=None,
                after=record,
                ip=ip,
                user_agent=user_agent,
            )
            return {"faq_id": record.id}

        faq_id = payload.get("id")
        if not faq_id:
            raise HTTPException(status_code=400, detail="Missing faq id")
        record = await session.get(Faq, int(faq_id))
        if not record:
            raise HTTPException(status_code=404, detail="FAQ not found")

        if action.action_type == "faq.delete":
            before = FaqOut.model_validate(record)
            await session.delete(record)
            await session.commit()
            await record_audit(
                session,
                admin_id=admin_id,
                entity="faq",
                action="delete",
                before=before,
                after=None,
                ip=ip,
                user_agent=user_agent,
            )
            return {"faq_id": int(faq_id), "deleted": True}

        update_data = FaqUpdate(**payload).model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No FAQ changes provided")
        before = FaqOut.model_validate(record)
        for key, value in update_data.items():
            setattr(record, key, value)
        await session.commit()
        await record_audit(
            session,
            admin_id=admin_id,
            entity="faq",
            action="update",
            before=before,
            after=record,
            ip=ip,
            user_agent=user_agent,
        )
        return {"faq_id": record.id, "updated": list(update_data.keys())}

    if action.action_type.startswith("campaign."):
        if action.action_type == "campaign.create":
            data = CampaignCreate(**payload).model_dump()
            record = Campaign(**data)
            session.add(record)
            await session.commit()
            await record_audit(
                session,
                admin_id=admin_id,
                entity="campaign",
                action="create",
                before=None,
                after=record,
                ip=ip,
                user_agent=user_agent,
            )
            return {"campaign_id": record.id}

        campaign_id = payload.get("id")
        if not campaign_id:
            raise HTTPException(status_code=400, detail="Missing campaign id")
        record = await session.get(Campaign, int(campaign_id))
        if not record:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if action.action_type == "campaign.delete":
            before = CampaignOut.model_validate(record)
            await session.delete(record)
            await session.commit()
            await record_audit(
                session,
                admin_id=admin_id,
                entity="campaign",
                action="delete",
                before=before,
                after=None,
                ip=ip,
                user_agent=user_agent,
            )
            return {"campaign_id": int(campaign_id), "deleted": True}

        update_data = CampaignUpdate(**payload).model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No campaign changes provided")
        before = CampaignOut.model_validate(record)
        for key, value in update_data.items():
            setattr(record, key, value)
        await session.commit()
        await record_audit(
            session,
            admin_id=admin_id,
            entity="campaign",
            action="update",
            before=before,
            after=record,
            ip=ip,
            user_agent=user_agent,
        )
        return {"campaign_id": record.id, "updated": list(update_data.keys())}

    if action.action_type.startswith("product."):
        if action.action_type == "product.create":
            data = ProductCreate(**payload).model_dump()
            record = Product(**data)
            session.add(record)
            await session.commit()
            await record_audit(
                session,
                admin_id=admin_id,
                entity="product",
                action="create",
                before=None,
                after=record,
                ip=ip,
                user_agent=user_agent,
            )
            return {"product_id": record.id}

        product_id = payload.get("id")
        if not product_id:
            raise HTTPException(status_code=400, detail="Missing product id")
        record = await session.get(Product, int(product_id))
        if not record:
            raise HTTPException(status_code=404, detail="Product not found")

        if action.action_type == "product.delete":
            before = ProductOut.model_validate(record)
            await session.delete(record)
            await session.commit()
            await record_audit(
                session,
                admin_id=admin_id,
                entity="product",
                action="delete",
                before=before,
                after=None,
                ip=ip,
                user_agent=user_agent,
            )
            return {"product_id": int(product_id), "deleted": True}

        update_data = ProductUpdate(**payload).model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No product changes provided")
        before = ProductOut.model_validate(record)
        for key, value in update_data.items():
            setattr(record, key, value)
        await session.commit()
        await record_audit(
            session,
            admin_id=admin_id,
            entity="product",
            action="update",
            before=before,
            after=record,
            ip=ip,
            user_agent=user_agent,
        )
        return {"product_id": record.id, "updated": list(update_data.keys())}

    raise HTTPException(status_code=400, detail="Unsupported action type")


@router.get("/conversations", response_model=dict)
async def list_conversations(
    skip: int = 0,
    limit: int = 25,
    sort: str = "updated_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(AssistantConversation)

    if admin.role != "admin":
        query = query.where(AssistantConversation.admin_id == admin.id)
    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(AssistantConversation.id.in_(ids))
    if "admin_id" in filters and admin.role == "admin":
        query = query.where(AssistantConversation.admin_id == int(filters["admin_id"]))
    if "title" in filters:
        query = query.where(AssistantConversation.title.ilike(f"%{filters['title']}%"))
    if "from" in filters:
        try:
            start = datetime.fromisoformat(filters["from"])
            query = query.where(AssistantConversation.created_at >= start)
        except ValueError:
            pass
    if "to" in filters:
        try:
            end = datetime.fromisoformat(filters["to"])
            query = query.where(AssistantConversation.created_at <= end)
        except ValueError:
            pass

    sort_col = getattr(AssistantConversation, sort, AssistantConversation.updated_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [AssistantConversationOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.post("/conversations", response_model=AssistantConversationOut)
async def create_conversation(
    payload: AssistantConversationCreate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AssistantConversationOut:
    mode = payload.mode or settings.LLM_MODE or "hybrid"
    conversation = AssistantConversation(
        admin_id=admin.id,
        title=payload.title,
        context=payload.context,
        mode=mode if mode in {"hybrid", "openai", "deepseek"} else "hybrid",
    )
    session.add(conversation)
    await session.commit()
    return AssistantConversationOut.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=AssistantConversationOut)
async def get_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AssistantConversationOut:
    conversation = await _require_conversation(
        session,
        conversation_id,
        admin_id=admin.id,
        is_admin=admin.role == "admin",
    )
    return AssistantConversationOut.model_validate(conversation)


@router.put("/conversations/{conversation_id}", response_model=AssistantConversationOut)
async def update_conversation(
    conversation_id: int,
    payload: AssistantConversationUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AssistantConversationOut:
    conversation = await _require_conversation(
        session,
        conversation_id,
        admin_id=admin.id,
        is_admin=admin.role == "admin",
    )
    before = AssistantConversationOut.model_validate(conversation)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(conversation, key, value)
    await session.commit()
    await record_audit(
        session,
        admin_id=admin.id,
        entity="assistant_conversation",
        action="update",
        before=before,
        after=conversation,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return AssistantConversationOut.model_validate(conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=dict)
async def list_conversation_messages(
    conversation_id: int,
    skip: int = 0,
    limit: int = 200,
    sort: str = "created_at",
    order: str = "asc",
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    conversation = await _require_conversation(
        session,
        conversation_id,
        admin_id=admin.id,
        is_admin=admin.role == "admin",
    )

    query = select(AssistantMessage).where(
        AssistantMessage.conversation_id == conversation.id
    )
    sort_col = getattr(AssistantMessage, sort, AssistantMessage.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [AssistantMessageOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/actions", response_model=dict)
async def list_actions(
    skip: int = 0,
    limit: int = 25,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(AssistantAction)

    if admin.role != "admin":
        query = query.where(AssistantAction.admin_id == admin.id)
    if "status" in filters:
        query = query.where(AssistantAction.status == filters["status"])
    if "action_type" in filters:
        query = query.where(AssistantAction.action_type == filters["action_type"])
    if "conversation_id" in filters:
        query = query.where(
            AssistantAction.conversation_id == int(filters["conversation_id"])
        )
    if "admin_id" in filters and admin.role == "admin":
        query = query.where(AssistantAction.admin_id == int(filters["admin_id"]))

    sort_col = getattr(AssistantAction, sort, AssistantAction.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [AssistantActionOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.post("/actions", response_model=AssistantActionOut)
async def create_action(
    payload: AssistantActionCreate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AssistantActionOut:
    if payload.action_type not in ALLOWED_ACTION_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported action type")
    payload_data = dict(payload.payload or {})
    if payload.action_type.startswith("product."):
        payload_data = await _prepare_product_action_payload(
            session, payload.action_type, payload_data
        )
        if payload.action_type == "product.create" and not payload_data.get("page_url"):
            raise HTTPException(
                status_code=400,
                detail="product.create requires page_url. Provide a product URL.",
            )
        if payload.action_type in {"product.update", "product.delete"} and not payload_data.get("id"):
            raise HTTPException(
                status_code=400,
                detail="product.update/delete requires id or a valid product_id/page_url/slug.",
            )
    if payload.action_type in {"faq.update", "faq.delete"}:
        faq_id = (payload.payload or {}).get("id")
        if not faq_id:
            raise HTTPException(status_code=400, detail="faq.update/delete requires id.")
    if payload.action_type in {"campaign.update", "campaign.delete"}:
        campaign_id = (payload.payload or {}).get("id")
        if not campaign_id:
            raise HTTPException(
                status_code=400,
                detail="campaign.update/delete requires id.",
            )
    action = AssistantAction(
        conversation_id=payload.conversation_id,
        admin_id=admin.id,
        status="pending",
        action_type=payload.action_type,
        summary=payload.summary,
        payload_json=payload_data,
    )
    session.add(action)
    await session.commit()
    await session.refresh(action)
    return AssistantActionOut.model_validate(action)


@router.patch("/actions/{action_id}", response_model=AssistantActionOut)
async def update_action(
    action_id: int,
    payload: AssistantActionUpdate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> AssistantActionOut:
    action = await session.get(AssistantAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        await session.refresh(action)
        return AssistantActionOut.model_validate(action)

    if payload.summary is not None:
        action.summary = payload.summary
    if payload.payload is not None:
        payload_data = dict(payload.payload)
        if action.action_type.startswith("product."):
            payload_data = await _prepare_product_action_payload(
                session, action.action_type, payload_data
            )
            if action.action_type == "product.create" and not payload_data.get("page_url"):
                raise HTTPException(
                    status_code=400,
                    detail="product.create requires page_url. Provide a product URL.",
                )
            if action.action_type in {"product.update", "product.delete"} and not payload_data.get("id"):
                raise HTTPException(
                    status_code=400,
                    detail="product.update/delete requires id or a valid product_id/page_url/slug.",
                )
        action.payload_json = payload_data

    await session.commit()
    await session.refresh(action)
    return AssistantActionOut.model_validate(action)


@router.post("/actions/{action_id}/approve", response_model=AssistantActionOut)
async def approve_action(
    action_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> AssistantActionOut:
    action = await session.get(AssistantAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        await session.refresh(action)
        return AssistantActionOut.model_validate(action)

    if action.action_type.startswith("product."):
        payload_data = await _prepare_product_action_payload(
            session, action.action_type, dict(action.payload_json or {})
        )
        if payload_data != (action.payload_json or {}):
            action.payload_json = payload_data
            await session.commit()
            await session.refresh(action)

    action.status = "approved"
    action.approved_by = admin.id
    action.approved_at = utc_now()
    await session.commit()

    try:
        result = await _execute_action(session, action, admin.id, request)
    except Exception as exc:
        logger.warning("assistant_action_failed", action_id=action.id, error=str(exc))
        action.status = "failed"
        action.error = str(exc)
        await session.commit()
        await session.refresh(action)
        return AssistantActionOut.model_validate(action)

    action.status = "executed"
    action.result_json = result
    action.executed_at = utc_now()
    await session.commit()
    await session.refresh(action)
    return AssistantActionOut.model_validate(action)


@router.post("/actions/{action_id}/reject", response_model=AssistantActionOut)
async def reject_action(
    action_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> AssistantActionOut:
    action = await session.get(AssistantAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        await session.refresh(action)
        return AssistantActionOut.model_validate(action)
    action.status = "rejected"
    action.approved_by = admin.id
    action.approved_at = utc_now()
    await session.commit()
    await session.refresh(action)
    return AssistantActionOut.model_validate(action)


@router.get("/export")
async def export_history(
    format: str = "json",
    type: str = "messages",
    conversation_id: int | None = None,
    since: datetime | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
):
    export_type = type.lower()
    export_format = format.lower()
    if export_type not in EXPORT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported export type")
    if export_format not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    if export_type == "training" and export_format != "json":
        raise HTTPException(status_code=400, detail="Training export supports JSON only")

    conversations = await _get_export_conversations(
        session, admin, conversation_id, since
    )
    conv_ids = [item.id for item in conversations]

    if export_format == "json":
        payload: dict[str, Any] = {
            "generated_at": utc_now().isoformat(),
            "filters": {
                "conversation_id": conversation_id,
                "since": since.isoformat() if since else None,
                "type": export_type,
            },
        }
        if export_type in {"messages", "conversations", "actions", "training"}:
            payload["conversations"] = [
                AssistantConversationOut.model_validate(item).model_dump(mode="json")
                for item in conversations
            ]

        if export_type in {"messages", "training"}:
            if conv_ids:
                message_query = (
                    select(AssistantMessage)
                    .where(AssistantMessage.conversation_id.in_(conv_ids))
                    .order_by(AssistantMessage.created_at.asc())
                )
                if since:
                    message_query = message_query.where(AssistantMessage.created_at >= since)
                result = await session.execute(message_query)
                payload["messages"] = [
                    AssistantMessageOut.model_validate(item).model_dump(mode="json")
                    for item in result.scalars().all()
                ]
            elif admin.role == "admin" and not conversation_id:
                message_query = select(AssistantMessage).order_by(
                    AssistantMessage.created_at.asc()
                )
                if since:
                    message_query = message_query.where(AssistantMessage.created_at >= since)
                result = await session.execute(message_query)
                payload["messages"] = [
                    AssistantMessageOut.model_validate(item).model_dump(mode="json")
                    for item in result.scalars().all()
                ]
            else:
                payload["messages"] = []

        if export_type in {"actions", "training"}:
            if conv_ids:
                action_query = (
                    select(AssistantAction)
                    .where(AssistantAction.conversation_id.in_(conv_ids))
                    .order_by(AssistantAction.created_at.asc())
                )
                if since:
                    action_query = action_query.where(AssistantAction.created_at >= since)
            else:
                action_query = select(AssistantAction).order_by(
                    AssistantAction.created_at.asc()
                )
                if admin.role != "admin":
                    action_query = action_query.where(AssistantAction.admin_id == admin.id)
                if since:
                    action_query = action_query.where(AssistantAction.created_at >= since)
            result = await session.execute(action_query)
            payload["actions"] = [
                AssistantActionOut.model_validate(item).model_dump(mode="json")
                for item in result.scalars().all()
            ]

        return JSONResponse(content=payload)

    if export_type == "conversations":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "conversation_id",
                "admin_id",
                "title",
                "context",
                "mode",
                "last_message_at",
                "created_at",
                "updated_at",
            ]
        )
        for conversation in conversations:
            writer.writerow(
                [
                    conversation.id,
                    conversation.admin_id,
                    conversation.title or "",
                    conversation.context or "",
                    conversation.mode,
                    conversation.last_message_at.isoformat()
                    if conversation.last_message_at
                    else "",
                    conversation.created_at.isoformat() if conversation.created_at else "",
                    conversation.updated_at.isoformat() if conversation.updated_at else "",
                ]
            )
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=assistant_conversations.csv"},
        )

    if export_type == "actions":
        query = select(AssistantAction)
        if conv_ids:
            query = query.where(AssistantAction.conversation_id.in_(conv_ids))
        elif admin.role != "admin":
            query = query.where(AssistantAction.admin_id == admin.id)
        if since:
            query = query.where(AssistantAction.created_at >= since)
        query = query.order_by(AssistantAction.created_at.asc())
        result = await session.execute(query)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "action_id",
                "conversation_id",
                "admin_id",
                "status",
                "action_type",
                "summary",
                "payload_json",
                "result_json",
                "error",
                "approved_by",
                "approved_at",
                "executed_at",
                "created_at",
            ]
        )
        for action in result.scalars().all():
            writer.writerow(
                [
                    action.id,
                    action.conversation_id or "",
                    action.admin_id,
                    action.status,
                    action.action_type,
                    action.summary or "",
                    action.payload_json or {},
                    action.result_json or {},
                    action.error or "",
                    action.approved_by or "",
                    action.approved_at.isoformat() if action.approved_at else "",
                    action.executed_at.isoformat() if action.executed_at else "",
                    action.created_at.isoformat() if action.created_at else "",
                ]
            )
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=assistant_actions.csv"},
        )

    query = select(AssistantMessage)
    if conv_ids:
        query = query.where(AssistantMessage.conversation_id.in_(conv_ids))
    elif admin.role != "admin":
        query = query.join(
            AssistantConversation,
            AssistantMessage.conversation_id == AssistantConversation.id,
        ).where(AssistantConversation.admin_id == admin.id)
    if since:
        query = query.where(AssistantMessage.created_at >= since)
    query = query.order_by(AssistantMessage.created_at.asc())
    result = await session.execute(query)

    if not conversations and admin.role == "admin" and not conversation_id:
        conv_result = await session.execute(select(AssistantConversation))
        conversations = list(conv_result.scalars().all())
    conversation_map = {item.id: item for item in conversations}
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "conversation_id",
            "conversation_title",
            "conversation_context",
            "conversation_mode",
            "admin_id",
            "message_id",
            "role",
            "content",
            "provider",
            "truncated",
            "error",
            "created_at",
        ]
    )
    for message in result.scalars().all():
        conversation = conversation_map.get(message.conversation_id)
        writer.writerow(
            [
                message.conversation_id,
                conversation.title if conversation else "",
                conversation.context if conversation else "",
                conversation.mode if conversation else "",
                conversation.admin_id if conversation else "",
                message.id,
                message.role,
                message.content,
                message.provider or "",
                message.truncated,
                message.error or "",
                message.created_at.isoformat() if message.created_at else "",
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assistant_messages.csv"},
    )


@router.post("/chat", response_model=AssistantChatResponse)
async def chat_with_assistant(
    payload: AssistantChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AssistantChatResponse:
    settings_record = await _get_active_settings(session)
    max_history = (
        settings_record.max_history_messages
        if settings_record
        else settings.MAX_HISTORY_MESSAGES
    )
    max_output = (
        settings_record.max_output_chars if settings_record else settings.MAX_RESPONSE_CHARS
    )
    ai_mode = payload.mode or (settings_record.ai_mode if settings_record else None)
    if ai_mode not in {"hybrid", "openai", "deepseek"}:
        ai_mode = settings.LLM_MODE
    if ai_mode not in {"hybrid", "openai", "deepseek"}:
        ai_mode = "hybrid"

    cleaned = _sanitize_messages(
        [message.model_dump() for message in payload.messages],
        max_history,
    )
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one message is required")

    last_user_text = next(
        (msg["content"] for msg in reversed(cleaned) if msg["role"] == "user"),
        cleaned[-1]["content"],
    )

    is_admin = admin.role == "admin"
    conversation = None
    if payload.conversation_id:
        conversation = await _require_conversation(
            session,
            payload.conversation_id,
            admin_id=admin.id,
            is_admin=is_admin,
        )
    else:
        title = payload.title or last_user_text[:80]
        conversation = AssistantConversation(
            admin_id=admin.id,
            title=title,
            context=payload.context,
            mode=ai_mode,
        )
        session.add(conversation)
        await session.commit()

    if payload.title is not None:
        conversation.title = payload.title
    if payload.context is not None:
        conversation.context = payload.context
    conversation.mode = ai_mode
    conversation.last_message_at = utc_now()

    history_query = (
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.created_at.desc())
        .limit(max_history)
    )
    history_result = await session.execute(history_query)
    history_items = list(reversed(history_result.scalars().all()))

    system_prompt = load_prompt("admin_assistant.txt") or DEFAULT_ASSISTANT_PROMPT
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if payload.include_snapshot:
        snapshot = await _build_snapshot(session)
        llm_messages.append({"role": "system", "content": snapshot})

    if conversation.context:
        context = conversation.context.strip()
        if context:
            llm_messages.append({"role": "system", "content": f"Context: {context}"})

    matched_products = await match_products(
        session,
        last_user_text,
        limit=settings.PRODUCT_MATCH_LIMIT,
    )
    if matched_products:
        llm_messages.append(
            {"role": "system", "content": _build_product_context(matched_products)}
        )

    for item in history_items:
        if item.role not in {"user", "assistant"}:
            continue
        llm_messages.append({"role": item.role, "content": item.content})

    llm_messages.append({"role": "user", "content": last_user_text})

    normalized = NormalizedMessage(
        sender_id=str(admin.id),
        receiver_id=None,
        message_type="text",
        text=last_user_text,
        raw_payload={},
    )
    provider = choose_provider(normalized, ai_mode)

    user_message = AssistantMessage(
        conversation_id=conversation.id,
        role="user",
        content=last_user_text,
    )
    session.add(user_message)

    try:
        if ai_mode == "hybrid":
            reply_text, usage, provider_used = await generate_with_fallback(
                provider, llm_messages
            )
        else:
            reply_text, usage = await generate_reply(provider, llm_messages)
            provider_used = provider
    except LLMError as exc:
        logger.warning("assistant_llm_failed", provider=provider, error=str(exc))
        fallback = "The assistant is temporarily unavailable. Try again in a moment."
        assistant_message = AssistantMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=fallback,
            provider=provider,
            error=str(exc),
        )
        session.add(assistant_message)
        await session.commit()
        return AssistantChatResponse(
            conversation_id=conversation.id,
            reply=fallback,
            provider=provider,
            usage=None,
            truncated=False,
            error=str(exc),
        )

    truncated = False
    if max_output > 0 and len(reply_text) > max_output:
        reply_text = reply_text[:max_output].rstrip()
        truncated = True

    assistant_message = AssistantMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=reply_text,
        provider=provider_used,
        usage_json=usage,
        truncated=truncated,
    )
    session.add(assistant_message)
    await session.commit()

    if usage:
        await record_usage(session, usage, provider_used)

    if not conversation.title:
        conversation.title = last_user_text[:80]
        await session.commit()

    return AssistantChatResponse(
        conversation_id=conversation.id,
        reply=reply_text,
        provider=provider_used,
        usage=usage,
        truncated=truncated,
        error=None,
    )
