from __future__ import annotations

from collections import Counter
from datetime import timedelta
import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, func, Integer, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.deps import require_role
from app.core.database import get_session
from app.models.app_log import AppLog
from app.models.behavior_event import BehaviorEvent
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.admin_policy_memory import (
    format_admin_policy_memory,
    get_admin_policy_memory,
    reset_admin_policy_memory,
    store_admin_policy_memory,
)
from app.utils.time import utc_now

router = APIRouter(prefix="/admin/analytics", tags=["admin"])

_GENERIC_ASSISTANT_RE = re.compile(
    r"(چطور می.?توانم.*کمک|سوالی درباره محصولات|برای معرفی دقیق.?تر|به نظر می.?رسد که شما (عکسی|تصویری) ارسال کرده.?اید)",
    re.IGNORECASE,
)


class PolicyMemoryCreate(BaseModel):
    text: str = Field(min_length=6, max_length=1200)
    priority: str | None = Field(default=None, max_length=20)
    kind: str | None = Field(default=None, max_length=20)


@router.get("/summary", response_model=dict)
async def analytics_summary(
    days: int = Query(default=30, ge=1, le=180),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    since = utc_now() - timedelta(days=days)

    # Messages per day (user messages)
    messages_query = (
        select(func.date_trunc("day", Message.created_at).label("day"), func.count())
        .where(Message.created_at >= since)
        .where(Message.role == "user")
        .group_by(func.date_trunc("day", Message.created_at))
        .order_by(func.date_trunc("day", Message.created_at).desc())
    )
    result = await session.execute(messages_query)
    messages_per_day = [
        {"date": row[0].date().isoformat(), "count": row[1]} for row in result.all()
    ]

    # Avg latency
    latency_query = (
        select(func.avg(cast(AppLog.data["latency_ms"].astext, Integer)))
        .where(AppLog.event_type == "llm_latency")
        .where(AppLog.created_at >= since)
    )
    avg_latency = await session.scalar(latency_query)

    # Top intents
    intent_query = (
        select(
            AppLog.data["intent"].astext,
            func.count(),
        )
        .where(AppLog.event_type == "intent_detected")
        .where(AppLog.created_at >= since)
        .group_by(AppLog.data["intent"].astext)
        .order_by(func.count().desc())
        .limit(10)
    )
    result = await session.execute(intent_query)
    top_intents = [
        {"intent": row[0] or "unknown", "count": row[1]} for row in result.all()
    ]

    # Top patterns
    pattern_query = (
        select(BehaviorEvent.pattern, func.count())
        .where(BehaviorEvent.created_at >= since)
        .group_by(BehaviorEvent.pattern)
        .order_by(func.count().desc())
        .limit(10)
    )
    result = await session.execute(pattern_query)
    top_patterns = [
        {"pattern": row[0], "count": row[1]} for row in result.all()
    ]

    # Ready-to-buy count
    ready_count = await session.scalar(
        select(func.count())
        .select_from(BehaviorEvent)
        .where(BehaviorEvent.pattern == "ready_to_buy")
        .where(BehaviorEvent.created_at >= since)
    )

    # Abandoned rate
    total_conversations = await session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.last_user_message_at.is_not(None))
        .where(Conversation.last_user_message_at >= since)
    )
    abandoned_conversations = await session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.last_user_message_at.is_not(None))
        .where(Conversation.last_user_message_at >= since)
        .where(
            (Conversation.last_bot_message_at.is_(None))
            | (Conversation.last_bot_message_at < Conversation.last_user_message_at)
        )
    )
    total_conversations = total_conversations or 0
    abandoned_conversations = abandoned_conversations or 0
    abandoned_rate = (
        abandoned_conversations / total_conversations
        if total_conversations
        else 0.0
    )

    # Top search keywords from product_matched logs
    keyword_counter: Counter[str] = Counter()
    result = await session.execute(
        select(AppLog.data["query"].astext)
        .where(AppLog.event_type == "product_matched")
        .where(AppLog.created_at >= since)
        .order_by(AppLog.created_at.desc())
        .limit(200)
    )
    for (query_text,) in result.all():
        if not query_text:
            continue
        for token in str(query_text).split():
            if len(token) < 2:
                continue
            keyword_counter[token] += 1
    top_keywords = [
        {"keyword": key, "count": count}
        for key, count in keyword_counter.most_common(10)
    ]

    return {
        "messages_per_day": messages_per_day,
        "avg_latency_ms": int(avg_latency) if avg_latency else None,
        "top_intents": top_intents,
        "top_patterns": top_patterns,
        "ready_to_buy": ready_count or 0,
        "abandoned": {
            "total": total_conversations,
            "abandoned": abandoned_conversations,
            "rate": round(abandoned_rate, 3),
        },
        "top_keywords": top_keywords,
    }


@router.get("/conversation-quality", response_model=dict)
async def conversation_quality_summary(
    days: int = Query(default=30, ge=1, le=180),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    since = utc_now() - timedelta(days=days)

    total_user_messages = (
        await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.role == "user")
            .where(Message.created_at >= since)
        )
        or 0
    )
    total_assistant_messages = (
        await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.role == "assistant")
            .where(Message.created_at >= since)
        )
        or 0
    )
    image_user_messages = (
        await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.role == "user")
            .where(Message.type.in_(["media", "image", "photo"]))
            .where(Message.created_at >= since)
        )
        or 0
    )

    loop_events = (
        await session.scalar(
            select(func.count())
            .select_from(AppLog)
            .where(AppLog.event_type == "loop_detected")
            .where(AppLog.created_at >= since)
        )
        or 0
    )
    guardrail_rewrites = (
        await session.scalar(
            select(func.count())
            .select_from(AppLog)
            .where(AppLog.event_type == "reply_rewritten_by_guardrail")
            .where(AppLog.created_at >= since)
        )
        or 0
    )
    hallucination_prevented = (
        await session.scalar(
            select(func.count())
            .select_from(AppLog)
            .where(AppLog.event_type == "hallucination_prevented")
            .where(AppLog.created_at >= since)
        )
        or 0
    )

    assistant_text_rows = await session.execute(
        select(Message.content_text)
        .where(Message.role == "assistant")
        .where(Message.created_at >= since)
        .where(Message.content_text.is_not(None))
        .order_by(Message.created_at.desc())
        .limit(3000)
    )
    assistant_texts = [
        str(text).strip()
        for (text,) in assistant_text_rows.all()
        if isinstance(text, str) and text.strip()
    ]
    assistant_sample_size = len(assistant_texts)
    generic_assistant_count = sum(
        1 for text in assistant_texts if _GENERIC_ASSISTANT_RE.search(text)
    )

    top_templates = Counter(assistant_texts).most_common(15)
    repetitive_templates = [
        {"text": text[:220], "count": count}
        for text, count in top_templates
        if count >= 3
    ][:8]

    intent_rows = await session.execute(
        select(AppLog.data["intent"].astext)
        .where(AppLog.event_type == "intent_detected")
        .where(AppLog.created_at >= since)
        .limit(5000)
    )
    intents = [str(intent or "unknown") for (intent,) in intent_rows.all()]
    unknown_intents = sum(
        1 for intent in intents if intent.lower().strip() in {"unknown", "smalltalk"}
    )
    total_intents = len(intents)

    unresolved_conversations = (
        await session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.last_user_message_at.is_not(None))
            .where(Conversation.last_user_message_at >= since)
            .where(
                (Conversation.last_bot_message_at.is_(None))
                | (Conversation.last_bot_message_at < Conversation.last_user_message_at)
            )
        )
        or 0
    )

    generic_rate = (
        round(generic_assistant_count / assistant_sample_size, 3)
        if assistant_sample_size
        else 0.0
    )
    unknown_intent_rate = (
        round(unknown_intents / total_intents, 3) if total_intents else 0.0
    )
    loop_rate = (
        round(loop_events / total_assistant_messages, 3)
        if total_assistant_messages
        else 0.0
    )

    actions: list[str] = []
    if generic_rate >= 0.12:
        actions.append("کاهش پاسخ‌های generic: فعال‌سازی بازنویسی پویا و تنوع لحن")
    if unknown_intent_rate >= 0.2:
        actions.append("اصلاح intent routing: افزودن کلیدواژه‌های محاوره‌ای واقعی")
    if loop_rate >= 0.08:
        actions.append("تقویت loop-breaker: افزایش تنوع پاسخ و مسیر خروج قطعی")
    if image_user_messages and hallucination_prevented < max(1, image_user_messages // 20):
        actions.append("سخت‌گیری بیشتر روی grounding قیمت/موجودی در سناریو تصویر")
    if not actions:
        actions.append("وضعیت کیفیت مکالمه پایدار است؛ پایش هفتگی کافی است.")

    return {
        "window_days": days,
        "counts": {
            "user_messages": total_user_messages,
            "assistant_messages": total_assistant_messages,
            "assistant_sample_size": assistant_sample_size,
            "user_image_messages": image_user_messages,
            "loop_events": loop_events,
            "guardrail_rewrites": guardrail_rewrites,
            "hallucination_prevented": hallucination_prevented,
            "unknown_intents": unknown_intents,
            "total_intents": total_intents,
            "unresolved_conversations": unresolved_conversations,
            "generic_assistant_messages": generic_assistant_count,
        },
        "rates": {
            "generic_reply_rate": generic_rate,
            "unknown_intent_rate": unknown_intent_rate,
            "loop_rate": loop_rate,
        },
        "top_repetitive_templates": repetitive_templates,
        "recommended_actions": actions,
    }


@router.get("/policy-memory", response_model=dict)
async def list_policy_memory(
    limit: int = Query(default=12, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    items = await get_admin_policy_memory(session, limit=limit)
    return {
        "data": [
            {
                "text": item.text,
                "priority": item.priority,
                "kind": item.kind,
                "source": item.source,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "conversation_id": item.conversation_id,
                "message_id": item.message_id,
            }
            for item in items
        ],
        "formatted": format_admin_policy_memory(items),
    }


@router.post("/policy-memory", response_model=dict)
async def create_policy_memory(
    payload: PolicyMemoryCreate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    created = await store_admin_policy_memory(
        session,
        text=payload.text,
        source=f"admin_api:{admin.username}",
        priority_override=payload.priority,
        kind_override=payload.kind,
    )
    if created:
        await session.commit()
    return {"created": bool(created)}


@router.post("/policy-memory/reset", response_model=dict)
async def clear_policy_memory(
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    await reset_admin_policy_memory(session, source=f"admin_api:{admin.username}")
    await session.commit()
    return {"ok": True}
