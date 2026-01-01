from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CampaignBase(BaseModel):
    title: str
    body: str
    discount_code: str | None = None
    link: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    active: bool = True
    priority: int = 0


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    discount_code: str | None = None
    link: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    active: bool | None = None
    priority: int | None = None


class CampaignOut(CampaignBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
