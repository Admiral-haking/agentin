from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BotSettingsUpdate(BaseModel):
    ai_mode: str | None = None
    max_output_chars: int | None = None
    max_history_messages: int | None = None
    system_prompt: str | None = None
    fallback_text: str | None = None
    active: bool | None = None


class BotSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ai_mode: str
    max_output_chars: int
    max_history_messages: int
    system_prompt: str | None = None
    fallback_text: str | None = None
    language: str | None = None
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
