from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.product_taxonomy import infer_tags

CROSS_SELL_MAP: dict[str, list[str]] = {
    "کفش": ["جوراب", "لوازم جانبی", "اکسسوری"],
    "صندل و دمپایی": ["جوراب", "لوازم جانبی"],
    "کیف": ["اکسسوری", "لوازم جانبی"],
    "عطر و ادکلن": ["بادی اسپلش", "اسپری"],
    "ادکلن": ["بادی اسپلش", "اسپری"],
    "آرایشی و بهداشتی": ["آرایشی", "بهداشتی"],
    "آرایشی": ["بهداشتی"],
    "بهداشتی": ["آرایشی"],
}


def _extract_categories(products: Iterable[Product]) -> list[str]:
    categories: list[str] = []
    for product in products:
        text = " ".join(
            part
            for part in [product.slug, product.title, product.description, product.product_id]
            if part
        )
        tags = infer_tags(text)
        categories.extend(tags.categories)
    return categories


async def find_cross_sell_product(
    session: AsyncSession,
    matched_products: list[Product],
) -> Product | None:
    if not matched_products:
        return None
    categories = _extract_categories(matched_products)
    if not categories:
        return None
    target_keywords: list[str] = []
    for category in categories:
        target_keywords.extend(CROSS_SELL_MAP.get(category, []))
    if not target_keywords:
        return None

    conditions = []
    for keyword in list(dict.fromkeys(target_keywords)):
        like = f"%{keyword}%"
        conditions.extend(
            [
                Product.title.ilike(like),
                Product.slug.ilike(like),
                Product.description.ilike(like),
            ]
        )
    if not conditions:
        return None

    query = (
        select(Product)
        .where(or_(*conditions))
        .order_by(Product.updated_at.desc())
        .limit(5)
    )
    result = await session.execute(query)
    candidates = list(result.scalars().all())
    if not candidates:
        return None

    matched_ids = {product.id for product in matched_products}
    for candidate in candidates:
        if candidate.id in matched_ids:
            continue
        return candidate
    return None
