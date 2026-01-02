from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in tokens if len(token) >= 3]


def _score_product(product: Product, tokens: list[str]) -> int:
    haystack = " ".join(
        part for part in [product.slug, product.title, product.description] if part
    ).lower()
    return sum(1 for token in tokens if token in haystack)


async def match_products(
    session: AsyncSession,
    text: str | None,
    limit: int | None = None,
) -> list[Product]:
    if not settings.PRODUCTS_FEATURE_ENABLED:
        return []
    if not text:
        return []
    tokens = _tokenize(text)
    if not tokens:
        return []
    conditions = []
    for token in tokens:
        like = f"%{token}%"
        conditions.extend(
            [
                Product.slug.ilike(like),
                Product.title.ilike(like),
                Product.description.ilike(like),
            ]
        )
    if not conditions:
        return []

    query = (
        select(Product)
        .where(or_(*conditions))
        .order_by(Product.updated_at.desc())
        .limit(settings.PRODUCT_MATCH_CANDIDATES)
    )
    result = await session.execute(query)
    candidates = list(result.scalars().all())
    scored: list[tuple[int, datetime | None, Product]] = []
    for product in candidates:
        score = _score_product(product, tokens)
        if score <= 0:
            continue
        scored.append((score, product.updated_at, product))

    scored.sort(
        key=lambda item: (item[0], item[1] or datetime.min), reverse=True
    )
    max_items = limit if limit is not None else settings.PRODUCT_MATCH_LIMIT
    return [item[2] for item in scored[:max_items]]
