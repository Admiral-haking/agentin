from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    last_user_message_at: datetime | None = None
    last_bot_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
