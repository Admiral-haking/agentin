from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from app.models.audit_log import AuditLog


def _serialize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, set):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(val) for key, val in value.items()}
    return value


def _to_dict(value: object | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _serialize(value)
    if isinstance(value, list):
        return _serialize(value)
    if hasattr(value, "model_dump"):
        return _serialize(value.model_dump(mode="json"))
    try:
        mapper = inspect(value)
        payload = {attr.key: getattr(value, attr.key) for attr in mapper.mapper.column_attrs}
        return _serialize(payload)
    except Exception:
        if hasattr(value, "__dict__"):
            payload = {
                key: val
                for key, val in value.__dict__.items()
                if not key.startswith("_")
            }
            return _serialize(payload)
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
