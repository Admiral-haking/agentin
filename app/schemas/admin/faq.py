from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class FaqBase(BaseModel):
    question: str
    answer: str
    tags: list[str] | None = None
    verified: bool = False
    category: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return None


class FaqCreate(FaqBase):
    pass


class FaqUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    tags: list[str] | None = None
    verified: bool | None = None
    category: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value: Any) -> list[str] | None:
        return FaqBase.parse_tags(value)


class FaqOut(FaqBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
