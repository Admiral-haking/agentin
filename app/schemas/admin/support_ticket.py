from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SupportTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    conversation_id: int | None = None
    status: str
    summary: str | None = None
    last_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupportTicketUpdate(BaseModel):
    status: str | None = None
    summary: str | None = None
    last_message: str | None = None
