from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    type: str
    content_text: str | None = None
    media_url: str | None = None
    payload_json: dict | None = None
    created_at: datetime | None = None
