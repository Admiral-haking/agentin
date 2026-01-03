from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_STOPWORDS = {
    "محصول",
    "محصولات",
    "کالا",
    "قیمت",
    "خرید",
    "سفارش",
    "مدل",
    "لیست",
    "product",
    "products",
    "price",
    "buy",
    "order",
}


def _tokenize(text: str) -> list[str]:
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [
        token
        for token in tokens
        if len(token) >= 3 and token not in _STOPWORDS
    ]


def tokenize_query(text: str | None) -> list[str]:
    if not text:
        return []
    return _tokenize(text)


def _single_token_exact_match(product: Product, token: str) -> bool:
    candidates = [product.slug, product.product_id, product.title]
    for value in candidates:
        if not value:
            continue
        parts = re.split(r"[-_\\s]+", value.lower())
        if token in parts:
            return True
    return False


def _meets_threshold(score: int, tokens: list[str], product: Product) -> bool:
    if not tokens:
        return False
    if len(tokens) >= 2:
        return score >= settings.PRODUCT_MATCH_MIN_SCORE
    token = tokens[0]
    if len(token) < settings.PRODUCT_MATCH_SINGLE_TOKEN_MIN_LEN:
        return False
    return _single_token_exact_match(product, token)


def _score_product(product: Product, tokens: list[str]) -> int:
    haystack = " ".join(
        part
        for part in [
            product.slug,
            product.title,
            product.description,
            product.product_id,
        ]
        if part
    ).lower()
    return sum(1 for token in tokens if token in haystack)


def _matched_tokens(product: Product, tokens: list[str]) -> list[str]:
    haystack = " ".join(
        part
        for part in [
            product.slug,
            product.title,
            product.description,
            product.product_id,
        ]
        if part
    ).lower()
    return [token for token in tokens if token in haystack]


@dataclass(frozen=True)
class ProductMatch:
    product: Product
    score: int
    token_count: int
    matched_tokens: tuple[str, ...]


async def match_products(
    session: AsyncSession,
    text: str | None,
    limit: int | None = None,
) -> list[Product]:
    matches = await match_products_with_scores(session, text, limit=limit)
    return [match.product for match in matches]


async def match_products_with_scores(
    session: AsyncSession,
    text: str | None,
    limit: int | None = None,
) -> list[ProductMatch]:
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
                Product.product_id.ilike(like),
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
    scored: list[tuple[int, datetime | None, Product, list[str]]] = []
    for product in candidates:
        score = _score_product(product, tokens)
        if score <= 0:
            continue
        if not _meets_threshold(score, tokens, product):
            continue
        matched = _matched_tokens(product, tokens)
        scored.append((score, product.updated_at, product, matched))

    scored.sort(
        key=lambda item: (item[0], item[1] or datetime.min), reverse=True
    )
    max_items = limit if limit is not None else settings.PRODUCT_MATCH_LIMIT
    return [
        ProductMatch(
            product=item[2],
            score=item[0],
            token_count=len(tokens),
            matched_tokens=tuple(item[3]),
        )
        for item in scored[:max_items]
    ]
