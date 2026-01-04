from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    username: str | None = None
    follow_status: str | None = None
    follower_count: int | None = None
    is_vip: bool | None = None
    vip_score: int | None = None
    followup_opt_out: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserUpdate(BaseModel):
    is_vip: bool | None = None
    vip_score: int | None = None
    followup_opt_out: bool | None = None


class UserImportItem(BaseModel):
    external_id: str = Field(min_length=1)
    username: str | None = None
    follow_status: str | None = None
    follower_count: int | None = None
    profile_json: dict | None = None


class UserImportPayload(BaseModel):
    contacts: list[UserImportItem] = Field(min_length=1)
