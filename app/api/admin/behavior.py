from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.user import User
from app.schemas.admin.behavior import UserBehaviorOut

router = APIRouter(prefix="/admin/behavior", tags=["admin"])


def _extract_behavior(user: User) -> UserBehaviorOut:
    behavior = {}
    if isinstance(user.profile_json, dict):
        behavior = user.profile_json.get("behavior") or {}
    return UserBehaviorOut(
        id=user.id,
        external_id=user.external_id,
        username=user.username,
        last_pattern=behavior.get("last_pattern"),
        confidence=behavior.get("confidence"),
        updated_at=_parse_dt(behavior.get("updated_at")),
        last_reason=behavior.get("last_reason"),
        last_message=behavior.get("last_message"),
        summary=behavior.get("summary"),
        recent=behavior.get("recent"),
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("/users", response_model=dict)
async def list_user_behaviors(
    skip: int = 0,
    limit: int = 25,
    sort: str = "updated_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(User)
    if "external_id" in filters:
        query = query.where(User.external_id.ilike(f"%{filters['external_id']}%"))
    if "username" in filters:
        query = query.where(User.username.ilike(f"%{filters['username']}%"))

    sort_col = getattr(User, sort, User.updated_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [_extract_behavior(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/users/{user_id}", response_model=UserBehaviorOut)
async def get_user_behavior(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> UserBehaviorOut:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _extract_behavior(user)
