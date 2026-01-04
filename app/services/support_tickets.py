from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_ticket import SupportTicket
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
