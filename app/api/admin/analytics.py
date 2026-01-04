from __future__ import annotations

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, func, Integer, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_session
from app.models.app_log import AppLog
from app.models.behavior_event import BehaviorEvent
from app.models.conversation import Conversation
from app.models.message import Message
from app.utils.time import utc_now

router = APIRouter(prefix="/admin/analytics", tags=["admin"])


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
