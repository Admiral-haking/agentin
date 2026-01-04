from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.schemas.admin.support_ticket import SupportTicketOut, SupportTicketUpdate
from app.utils.time import utc_now

router = APIRouter(prefix="/admin/tickets", tags=["admin"])


@router.get("", response_model=dict)
async def list_tickets(
    skip: int = 0,
    limit: int = 25,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(SupportTicket)

    if "status" in filters:
        query = query.where(SupportTicket.status == filters["status"])
    if "user_id" in filters:
        query = query.where(SupportTicket.user_id == int(filters["user_id"]))
    if "conversation_id" in filters:
        query = query.where(
            SupportTicket.conversation_id == int(filters["conversation_id"])
        )
    if "external_id" in filters:
        query = query.join(User, User.id == SupportTicket.user_id).where(
            User.external_id.ilike(f"%{filters['external_id']}%")
        )

    sort_col = getattr(SupportTicket, sort, SupportTicket.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [SupportTicketOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{ticket_id}", response_model=SupportTicketOut)
async def get_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> SupportTicketOut:
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return SupportTicketOut.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=SupportTicketOut)
async def update_ticket(
    ticket_id: int,
    payload: SupportTicketUpdate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> SupportTicketOut:
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)
    ticket.updated_at = utc_now()
    await session.commit()
    return SupportTicketOut.model_validate(ticket)


@router.put("/{ticket_id}", response_model=SupportTicketOut)
async def replace_ticket(
    ticket_id: int,
    payload: SupportTicketUpdate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> SupportTicketOut:
    return await update_ticket(ticket_id, payload, session, admin)
