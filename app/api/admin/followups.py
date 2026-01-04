from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.followup_task import FollowupTask
from app.schemas.admin.followup import FollowupTaskOut, FollowupTaskUpdate

router = APIRouter(prefix="/admin/followups", tags=["admin"])


@router.get("", response_model=dict)
async def list_followups(
    skip: int = 0,
    limit: int = 25,
    sort: str = "scheduled_for",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(FollowupTask)
    if "status" in filters:
        query = query.where(FollowupTask.status == filters["status"])
    if "user_id" in filters:
        query = query.where(FollowupTask.user_id == int(filters["user_id"]))
    if "conversation_id" in filters:
        query = query.where(
            FollowupTask.conversation_id == int(filters["conversation_id"])
        )

    sort_col = getattr(FollowupTask, sort, FollowupTask.scheduled_for)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [FollowupTaskOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{task_id}", response_model=FollowupTaskOut)
async def get_followup(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> FollowupTaskOut:
    task = await session.get(FollowupTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Followup task not found")
    return FollowupTaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=FollowupTaskOut)
async def update_followup(
    task_id: int,
    payload: FollowupTaskUpdate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> FollowupTaskOut:
    task = await session.get(FollowupTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Followup task not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    await session.commit()
    return FollowupTaskOut.model_validate(task)


@router.put("/{task_id}", response_model=FollowupTaskOut)
async def replace_followup(
    task_id: int,
    payload: FollowupTaskUpdate,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> FollowupTaskOut:
    return await update_followup(task_id, payload, session, admin)
