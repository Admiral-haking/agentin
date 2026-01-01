from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from app.models.audit_log import AuditLog


def _to_dict(value: object | None) -> dict | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    try:
        mapper = inspect(value)
        return {attr.key: getattr(value, attr.key) for attr in mapper.mapper.column_attrs}
    except Exception:
        if hasattr(value, "__dict__"):
            return {
                key: val
                for key, val in value.__dict__.items()
                if not key.startswith("_")
            }
    return None


async def record_audit(
    session: AsyncSession,
    admin_id: int | None,
    entity: str,
    action: str,
    before: object | None,
    after: object | None,
    ip: str | None,
    user_agent: str | None,
) -> None:
    log = AuditLog(
        admin_id=admin_id,
        entity=entity,
        action=action,
        before_json=_to_dict(before),
        after_json=_to_dict(after),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(log)
    await session.commit()
