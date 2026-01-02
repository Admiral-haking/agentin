from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.product import ProductAvailability


class ProductBase(BaseModel):
    product_id: str | None = None
    slug: str | None = None
    page_url: str
    title: str | None = None
    description: str | None = None
    images: list[str] | None = None
    price: int | None = None
    old_price: int | None = None
    availability: ProductAvailability = ProductAvailability.unknown
    lastmod: datetime | None = None
    source_flags: dict[str, bool] | None = None

    @field_validator("images", mode="before")
    @classmethod
    def parse_images(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    product_id: str | None = None
    slug: str | None = None
    page_url: str | None = None
    title: str | None = None
    description: str | None = None
    images: list[str] | None = None
    price: int | None = None
    old_price: int | None = None
    availability: ProductAvailability | None = None
    lastmod: datetime | None = None
    source_flags: dict[str, bool] | None = None

    @field_validator("images", mode="before")
    @classmethod
    def parse_images(cls, value: Any) -> list[str] | None:
        return ProductBase.parse_images(value)


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
