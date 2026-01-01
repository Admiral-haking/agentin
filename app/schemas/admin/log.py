from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    event_type: str
    message: str | None = None
    data: dict | None = None
    created_at: datetime | None = None
