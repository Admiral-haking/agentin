from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product
from app.services.product_taxonomy import infer_tags

_CACHE_TS: float = 0.0
_CACHE_SNAPSHOT: "CatalogSnapshot | None" = None


@dataclass(frozen=True)
class CatalogSnapshot:
    created_at: float
    product_count: int
    category_counts: dict[str, int]
    gender_counts: dict[str, int]
    style_counts: dict[str, int]
    material_counts: dict[str, int]
    min_price: int | None
    max_price: int | None
    recent_products: list[dict[str, Any]]
    summary: str


def _format_price(value: int | None) -> str:
    if value is None:
        return "نامشخص"
    return f"{value:,}"


def _availability_label(value: str | None) -> str:
    if value == "instock":
        return "موجود"
    if value == "outofstock":
        return "ناموجود"
    return "نامشخص"


def _build_summary(snapshot: CatalogSnapshot) -> str:
    lines: list[str] = ["[CATALOG]"]
    lines.append(f"تعداد کل محصولات: {snapshot.product_count}")

    def _top_items(counter: dict[str, int], label: str) -> None:
        if not counter:
            return
        top = sorted(counter.items(), key=lambda item: item[1], reverse=True)
        top = top[: settings.PRODUCT_CATALOG_TOP_CATEGORIES]
        joined = "، ".join(f"{name}({count})" for name, count in top)
        lines.append(f"{label}: {joined}")

    _top_items(snapshot.category_counts, "دسته‌های پرتکرار")
    _top_items(snapshot.gender_counts, "جنسیت پرتکرار")
    _top_items(snapshot.style_counts, "سبک پرتکرار")
    _top_items(snapshot.material_counts, "جنس پرتکرار")

    if snapshot.min_price is not None or snapshot.max_price is not None:
        min_price = _format_price(snapshot.min_price)
        max_price = _format_price(snapshot.max_price)
        lines.append(f"بازه قیمت (محصولات قیمت‌دار): {min_price} تا {max_price}")

    if snapshot.recent_products:
        lines.append("نمونه‌های به‌روز:")
        for item in snapshot.recent_products:
            parts = [
                item.get("title", "محصول"),
                f"قیمت: {item.get('price', 'نامشخص')}",
                f"موجودی: {item.get('availability', 'نامشخص')}",
            ]
            if item.get("link"):
                parts.append(f"لینک: {item['link']}")
            lines.append("- " + " | ".join(parts))

    return "\n".join(lines).strip()


async def build_catalog_snapshot(session: AsyncSession) -> CatalogSnapshot:
    result = await session.execute(select(Product))
    products = list(result.scalars().all())
    category_counts: Counter[str] = Counter()
    gender_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    material_counts: Counter[str] = Counter()

    min_price: int | None = None
    max_price: int | None = None

    for product in products:
        text = " ".join(
            part
            for part in [
                product.slug,
                product.title,
                product.description,
                product.product_id,
            ]
            if part
        )
        tags = infer_tags(text)
        category_counts.update(tags.categories)
        gender_counts.update(tags.genders)
        style_counts.update(tags.styles)
        material_counts.update(tags.materials)
        if product.price is not None:
            min_price = product.price if min_price is None else min(min_price, product.price)
            max_price = product.price if max_price is None else max(max_price, product.price)

    recent_sorted = sorted(
        products,
        key=lambda item: item.updated_at or datetime.min,
        reverse=True,
    )
    recent_products: list[dict[str, Any]] = []
    for product in recent_sorted[: settings.PRODUCT_CATALOG_RECENT_COUNT]:
        availability = (
            product.availability.value
            if hasattr(product.availability, "value")
            else str(product.availability)
        )
        recent_products.append(
            {
                "id": product.id,
                "title": product.title or product.slug or "محصول",
                "price": _format_price(product.price),
                "availability": _availability_label(availability),
                "link": product.page_url,
            }
        )

    snapshot = CatalogSnapshot(
        created_at=time.time(),
        product_count=len(products),
        category_counts=dict(category_counts),
        gender_counts=dict(gender_counts),
        style_counts=dict(style_counts),
        material_counts=dict(material_counts),
        min_price=min_price,
        max_price=max_price,
        recent_products=recent_products,
        summary="",
    )
    summary = _build_summary(snapshot)
    return CatalogSnapshot(**{**snapshot.__dict__, "summary": summary})


async def get_catalog_snapshot(session: AsyncSession) -> CatalogSnapshot | None:
    if not settings.PRODUCTS_FEATURE_ENABLED:
        return None
    ttl = settings.PRODUCT_CATALOG_TTL_SEC
    global _CACHE_TS, _CACHE_SNAPSHOT
    if ttl > 0 and _CACHE_SNAPSHOT and (time.monotonic() - _CACHE_TS) < ttl:
        return _CACHE_SNAPSHOT
    snapshot = await build_catalog_snapshot(session)
    _CACHE_SNAPSHOT = snapshot
    _CACHE_TS = time.monotonic()
    return snapshot


async def refresh_catalog_snapshot(session: AsyncSession) -> CatalogSnapshot | None:
    if not settings.PRODUCTS_FEATURE_ENABLED:
        return None
    snapshot = await build_catalog_snapshot(session)
    global _CACHE_TS, _CACHE_SNAPSHOT
    _CACHE_SNAPSHOT = snapshot
    _CACHE_TS = time.monotonic()
    return snapshot
