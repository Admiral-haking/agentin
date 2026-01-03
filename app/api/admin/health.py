from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_session
from app.models import AssistantAction
from app.models.app_log import AppLog
from app.models.product_sync_run import ProductSyncRun
from app.utils.time import utc_now

router = APIRouter(prefix="/admin/health", tags=["admin"])


@router.get("/report", response_model=dict)
async def health_report(
    window_hours: int = 24,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    since = utc_now() - timedelta(hours=max(window_hours, 1))

    errors_count = await session.scalar(
        select(func.count())
        .select_from(AppLog)
        .where(AppLog.level == "error")
        .where(AppLog.created_at >= since)
    )
    send_errors = await session.scalar(
        select(func.count())
        .select_from(AppLog)
        .where(AppLog.event_type == "send_error")
        .where(AppLog.created_at >= since)
    )
    llm_errors = await session.scalar(
        select(func.count())
        .select_from(AppLog)
        .where(AppLog.event_type == "llm_error")
        .where(AppLog.created_at >= since)
    )

    latency_avg = await session.scalar(
        select(func.avg(cast(AppLog.data["latency_ms"].astext, Integer)))
        .where(AppLog.event_type == "llm_latency")
        .where(AppLog.created_at >= since)
    )

    last_error = await session.execute(
        select(AppLog)
        .where(AppLog.level == "error")
        .order_by(AppLog.created_at.desc())
        .limit(1)
    )
    last_error_record = last_error.scalars().first()

    pending_actions = await session.scalar(
        select(func.count())
        .select_from(AssistantAction)
        .where(AssistantAction.status == "pending")
    )

    last_sync = await session.execute(
        select(ProductSyncRun).order_by(ProductSyncRun.started_at.desc()).limit(1)
    )
    last_sync_record = last_sync.scalars().first()

    return {
        "window_hours": window_hours,
        "errors_last_window": errors_count or 0,
        "send_errors_last_window": send_errors or 0,
        "llm_errors_last_window": llm_errors or 0,
        "llm_latency_avg_ms": int(latency_avg) if latency_avg else None,
        "pending_actions": pending_actions or 0,
        "last_error": {
            "id": last_error_record.id,
            "event_type": last_error_record.event_type,
            "message": last_error_record.message,
            "created_at": last_error_record.created_at,
        }
        if last_error_record
        else None,
        "last_product_sync": {
            "status": last_sync_record.status,
            "started_at": last_sync_record.started_at,
            "finished_at": last_sync_record.finished_at,
            "created_count": last_sync_record.created_count,
            "updated_count": last_sync_record.updated_count,
            "unchanged_count": last_sync_record.unchanged_count,
            "error_count": last_sync_record.error_count,
        }
        if last_sync_record
        else None,
    }
