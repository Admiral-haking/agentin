from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.app_log import AppLog
from app.schemas.admin.log import AppLogOut

router = APIRouter(prefix="/admin/logs", tags=["admin"])


@router.get("", response_model=dict)
async def list_logs(
    skip: int = 0,
    limit: int = 50,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(AppLog)

    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(AppLog.id.in_(ids))
    if "level" in filters:
        query = query.where(AppLog.level == filters["level"])
    if "event_type" in filters:
        query = query.where(AppLog.event_type == filters["event_type"])
    if "contains" in filters:
        query = query.where(AppLog.message.ilike(f"%{filters['contains']}%"))
    if "from" in filters:
        try:
            start = datetime.fromisoformat(filters["from"])
            query = query.where(AppLog.created_at >= start)
        except ValueError:
            pass
    if "to" in filters:
        try:
            end = datetime.fromisoformat(filters["to"])
            query = query.where(AppLog.created_at <= end)
        except ValueError:
            pass

    sort_col = getattr(AppLog, sort, AppLog.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [AppLogOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)
