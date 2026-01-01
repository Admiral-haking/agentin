from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class ProductBase(BaseModel):
    title: str
    category: str | None = None
    price_range: str | None = None
    sizes: list[str] | None = None
    colors: list[str] | None = None
    images: list[str] | None = None
    link: str | None = None
    in_stock: bool = True

    @field_validator("sizes", "colors", "images", mode="before")
    @classmethod
    def parse_list(cls, value: Any) -> list[str] | None:
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
    title: str | None = None
    category: str | None = None
    price_range: str | None = None
    sizes: list[str] | None = None
    colors: list[str] | None = None
    images: list[str] | None = None
    link: str | None = None
    in_stock: bool | None = None

    @field_validator("sizes", "colors", "images", mode="before")
    @classmethod
    def parse_list(cls, value: Any) -> list[str] | None:
        return ProductBase.parse_list(value)


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
