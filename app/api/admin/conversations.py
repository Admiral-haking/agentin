from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.admin.conversation import ConversationOut

router = APIRouter(prefix="/admin/conversations", tags=["admin"])


@router.get("", response_model=dict)
async def list_conversations(
    skip: int = 0,
    limit: int = 25,
    sort: str = "last_user_message_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(Conversation).join(User)

    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(Conversation.id.in_(ids))
    if "user_id" in filters:
        query = query.where(Conversation.user_id == int(filters["user_id"]))
    if "username" in filters:
        query = query.where(User.username.ilike(f"%{filters['username']}%"))
    if "status" in filters:
        query = query.where(Conversation.status == filters["status"])
    if "from" in filters:
        try:
            start = datetime.fromisoformat(filters["from"])
            query = query.where(Conversation.created_at >= start)
        except ValueError:
            pass
    if "to" in filters:
        try:
            end = datetime.fromisoformat(filters["to"])
            query = query.where(Conversation.created_at <= end)
        except ValueError:
            pass

    sort_col = getattr(Conversation, sort, Conversation.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [ConversationOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> ConversationOut:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationOut.model_validate(conversation)
