from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NormalizedMessage(BaseModel):
    sender_id: str
    receiver_id: str | None = None
    message_type: str
    text: str | None = None
    media_url: str | None = None
    audio_url: str | None = None
    is_admin: bool = False
    read_message_id: str | None = None
    username: str | None = None
    follow_status: str | None = None
    follower_count: int | None = None
    timestamp: datetime | None = None
    raw_payload: dict[str, Any]
