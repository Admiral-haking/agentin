from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.user import User
from app.models.user_behavior_profile import UserBehaviorProfile
from app.schemas.admin.behavior import UserBehaviorOut

router = APIRouter(prefix="/admin/behavior", tags=["admin"])


def _extract_behavior(user: User, profile: UserBehaviorProfile | None) -> UserBehaviorOut:
    history = []
    if profile and isinstance(profile.pattern_history, list):
        history = profile.pattern_history
    counts: Counter[str] = Counter()
    for item in history:
        if isinstance(item, dict) and item.get("pattern"):
            counts[str(item["pattern"])] += 1
    recent = []
    for item in history[-5:]:
        if isinstance(item, dict):
            recent.append(
                {
                    "pattern": item.get("pattern"),
                    "confidence": item.get("confidence"),
                    "reason": item.get("reason"),
                }
            )
    last_reason = None
    last_message = None
    if history:
        last_item = history[-1]
        if isinstance(last_item, dict):
            last_reason = last_item.get("reason")
            last_message = last_item.get("message") or last_item.get("last_message")
    updated_at = profile.updated_at if profile else user.updated_at
    return UserBehaviorOut(
        id=user.id,
        external_id=user.external_id,
        username=user.username,
        last_pattern=profile.last_pattern if profile else None,
        confidence=profile.confidence if profile else None,
        updated_at=updated_at,
        last_reason=last_reason,
        last_message=last_message,
        summary=dict(counts) if counts else None,
        recent=recent or None,
    )


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
    query = select(User, UserBehaviorProfile).outerjoin(
        UserBehaviorProfile, UserBehaviorProfile.user_id == User.id
    )
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
    items = []
    for user, profile in result.all():
        items.append(_extract_behavior(user, profile))
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
    profile = await session.get(UserBehaviorProfile, user_id)
    return _extract_behavior(user, profile)
