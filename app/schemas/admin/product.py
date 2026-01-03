from __future__ import annotations

import json
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
            items: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    items.append(item.strip())
                elif isinstance(item, dict):
                    for key in ("url", "contentUrl", "src", "@id"):
                        candidate = item.get(key)
                        if isinstance(candidate, str) and candidate.strip():
                            items.append(candidate.strip())
                    nested = item.get("image") or item.get("images")
                    nested_items = cls.parse_images(nested)
                    if nested_items:
                        items.extend(nested_items)
            return items or None
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.startswith("[") or cleaned.startswith("{"):
                try:
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None:
                    return cls.parse_images(parsed)
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        if isinstance(value, dict):
            for key in ("url", "contentUrl", "src", "@id"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return [candidate.strip()]
            nested = value.get("image") or value.get("images")
            return cls.parse_images(nested)
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
