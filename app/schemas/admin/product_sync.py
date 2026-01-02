from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductSyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: str
    torob_count: int | None = None
    sitemap_count: int | None = None
    created_count: int | None = None
    updated_count: int | None = None
    unchanged_count: int | None = None
    error_count: int | None = None
    error_message: str | None = None
