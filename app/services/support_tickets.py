from __future__ import annotations

from datetime import timedelta

from sqlalchemy import Integer, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_log import AppLog
from app.models.support_ticket import SupportTicket
from app.services.app_log_store import log_event
from app.utils.time import utc_now


async def get_or_create_ticket(
    session: AsyncSession,
    user_id: int,
    conversation_id: int | None,
    summary: str | None,
    last_message: str | None,
) -> SupportTicket:
    query = select(SupportTicket).where(SupportTicket.user_id == user_id)
    if conversation_id is not None:
        query = query.where(SupportTicket.conversation_id == conversation_id)
    query = query.where(SupportTicket.status.in_(["open", "pending"]))
    query = query.order_by(SupportTicket.created_at.desc()).limit(1)
    result = await session.execute(query)
    ticket = result.scalars().first()
    if ticket:
        if last_message:
            ticket.last_message = last_message[:2000]
        if summary and not ticket.summary:
            ticket.summary = summary[:2000]
        ticket.updated_at = utc_now()
        await session.commit()
        return ticket

    ticket = SupportTicket(
        user_id=user_id,
        conversation_id=conversation_id,
        status="open",
        summary=summary[:2000] if summary else None,
        last_message=last_message[:2000] if last_message else None,
    )
    session.add(ticket)
    await session.commit()
    return ticket


async def auto_escalate_loop_to_operator(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: int | None,
    loop_counter: int,
    threshold: int,
    cooldown_minutes: int,
    reason: str,
    last_message: str | None,
) -> SupportTicket | None:
    if conversation_id is None:
        return None
    effective_threshold = max(1, int(threshold))
    if loop_counter < effective_threshold:
        return None

    recent_query = (
        select(AppLog)
        .where(AppLog.event_type == "loop_escalated_to_operator")
        .where(cast(AppLog.data["conversation_id"].astext, Integer) == conversation_id)
        .order_by(AppLog.created_at.desc())
        .limit(1)
    )
    recent = (await session.execute(recent_query)).scalars().first()
    if (
        recent is not None
        and recent.created_at is not None
        and cooldown_minutes > 0
    ):
        delta = utc_now() - recent.created_at
        if delta < timedelta(minutes=cooldown_minutes):
            return None

    ticket = await get_or_create_ticket(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
        summary="ارجاع خودکار اپراتور (loop)",
        last_message=last_message,
    )
    await log_event(
        session,
        level="info",
        event_type="loop_escalated_to_operator",
        message="loop auto-escalated to operator",
        data={
            "ticket_id": ticket.id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "loop_counter": loop_counter,
            "threshold": effective_threshold,
            "reason": reason,
            "cooldown_minutes": cooldown_minutes,
        },
        commit=False,
    )
    await session.commit()
    return ticket
