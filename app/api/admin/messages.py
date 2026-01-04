from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.message import Message
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.admin.message import MessageOut

router = APIRouter(prefix="/admin/messages", tags=["admin"])


def _message_out(message: Message, conversation: Conversation | None, user: User | None) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        user_id=conversation.user_id if conversation else None,
        user_external_id=user.external_id if user else None,
        username=user.username if user else None,
        is_vip=user.is_vip if user else None,
        role=message.role,
        type=message.type,
        content_text=message.content_text,
        media_url=message.media_url,
        payload_json=message.payload_json,
        created_at=message.created_at,
    )


@router.get("", response_model=dict)
async def list_messages(
    skip: int = 0,
    limit: int = 25,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = (
        select(Message, Conversation, User)
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
    )

    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(Message.id.in_(ids))
    if "conversation_id" in filters:
        query = query.where(Message.conversation_id == int(filters["conversation_id"]))
    if "role" in filters:
        query = query.where(Message.role == filters["role"])
    if "type" in filters:
        query = query.where(Message.type == filters["type"])
    if "contains" in filters:
        query = query.where(Message.content_text.ilike(f"%{filters['contains']}%"))
    if "from" in filters:
        try:
            start = datetime.fromisoformat(filters["from"])
            query = query.where(Message.created_at >= start)
        except ValueError:
            pass
    if "to" in filters:
        try:
            end = datetime.fromisoformat(filters["to"])
            query = query.where(Message.created_at <= end)
        except ValueError:
            pass

    sort_col = getattr(Message, sort, Message.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [
        _message_out(message, conversation, user)
        for message, conversation, user in result.all()
    ]
    return list_response(items, total or 0)


@router.get("/{message_id}", response_model=MessageOut)
async def get_message(
    message_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> MessageOut:
    result = await session.execute(
        select(Message, Conversation, User)
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
        .where(Message.id == message_id)
        .limit(1)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    message, conversation, user = row
    return _message_out(message, conversation, user)
