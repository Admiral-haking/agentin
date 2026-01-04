from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FollowupTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    conversation_id: int | None = None
    status: str
    scheduled_for: datetime
    sent_at: datetime | None = None
    reason: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FollowupTaskUpdate(BaseModel):
    status: str | None = None
    scheduled_for: datetime | None = None
    reason: str | None = None
    payload: dict[str, Any] | None = None
