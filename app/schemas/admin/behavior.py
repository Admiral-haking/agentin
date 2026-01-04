from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserBehaviorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    username: str | None = None
    last_pattern: str | None = None
    confidence: float | None = None
    updated_at: datetime | None = None
    last_reason: str | None = None
    last_message: str | None = None
    summary: dict[str, int] | None = None
    recent: list[dict[str, Any]] | None = None


class AIContextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: dict[str, Any]
    context: str
    sections: dict[str, Any]
