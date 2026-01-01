from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_log import AppLog


async def log_event(
    session: AsyncSession,
    level: str,
    event_type: str,
    message: str | None = None,
    data: dict | None = None,
    commit: bool = True,
) -> None:
    log = AppLog(
        level=level,
        event_type=event_type,
        message=message,
        data=data,
    )
    session.add(log)
    if commit:
        await session.commit()
