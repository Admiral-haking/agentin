from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AISimulateIn(BaseModel):
    conversation_id: int = Field(gt=0)
    message: str | None = None


class AISimulateOut(BaseModel):
    draft_reply: str
    context_used: dict[str, Any]
    sources: dict[str, Any]
