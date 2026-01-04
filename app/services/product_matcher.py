from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product
from app.services.product_taxonomy import expand_query_terms, infer_tags

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
    "سایز",
    "میخوام",
    "می خوام",
    "میخواهم",
    "می خواهم",
    "می‌خوام",
    "می‌خواهم",
    "میگردم",
    "می‌گردم",
    "دنبال",
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
        if len(token) >= 3
        and token not in _STOPWORDS
        and not (token.isdigit() and len(token) <= 3)
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
    matched_tags: tuple[str, ...]


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
    query_tags = infer_tags(text)
    tokens = _tokenize(text)
    if not tokens and not (
        query_tags.categories
        or query_tags.genders
        or query_tags.materials
        or query_tags.styles
        or query_tags.colors
        or query_tags.sizes
    ):
        return []

    candidates: list[Product] = []
    if tokens:
        terms = expand_query_terms(text)
        terms = list(dict.fromkeys(tokens + terms))
        if len(terms) > settings.PRODUCT_MATCH_QUERY_TERMS:
            terms = terms[: settings.PRODUCT_MATCH_QUERY_TERMS]
        conditions = []
        for token in terms:
            like = f"%{token}%"
            conditions.extend(
                [
                    Product.slug.ilike(like),
                    Product.title.ilike(like),
                    Product.description.ilike(like),
                    Product.product_id.ilike(like),
                ]
            )
        if conditions:
            query = (
                select(Product)
                .where(or_(*conditions))
                .order_by(Product.updated_at.desc())
                .limit(settings.PRODUCT_MATCH_CANDIDATES)
            )
            result = await session.execute(query)
            candidates = list(result.scalars().all())

    if not candidates:
        query = (
            select(Product)
            .order_by(Product.updated_at.desc())
            .limit(settings.PRODUCT_MATCH_CANDIDATES)
        )
        result = await session.execute(query)
        candidates = list(result.scalars().all())
    scored: list[tuple[int, datetime | None, Product, list[str], list[str]]] = []
    for product in candidates:
        product_text = " ".join(
            part
            for part in [
                product.slug,
                product.title,
                product.description,
                product.product_id,
            ]
            if part
        )
        product_tags = infer_tags(product_text)
        if query_tags.categories and not set(query_tags.categories).intersection(
            product_tags.categories
        ):
            continue
        if query_tags.genders and not product_tags.genders:
            continue
        if query_tags.genders and product_tags.genders and not set(query_tags.genders).intersection(
            product_tags.genders
        ):
            continue
        if query_tags.materials and not set(query_tags.materials).intersection(
            product_tags.materials
        ):
            continue
        if query_tags.styles and not set(query_tags.styles).intersection(
            product_tags.styles
        ):
            continue

        token_score = _score_product(product, tokens)
        matched_tags: list[str] = []
        for label, values in (
            ("cat", set(query_tags.categories).intersection(product_tags.categories)),
            ("gen", set(query_tags.genders).intersection(product_tags.genders)),
            ("mat", set(query_tags.materials).intersection(product_tags.materials)),
            ("sty", set(query_tags.styles).intersection(product_tags.styles)),
            ("col", set(query_tags.colors).intersection(product_tags.colors)),
            ("siz", set(query_tags.sizes).intersection(product_tags.sizes)),
        ):
            for value in values:
                matched_tags.append(f"{label}:{value}")
        tag_bonus = len(matched_tags)
        if token_score <= 0 and tag_bonus <= 0:
            continue
        if token_score > 0 and not _meets_threshold(token_score, tokens, product):
            continue
        if token_score <= 0 and len(tokens) >= 2 and tag_bonus < 2:
            continue
        score = token_score + tag_bonus
        matched = _matched_tokens(product, tokens)
        scored.append((score, product.updated_at, product, matched, matched_tags))

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
            matched_tags=tuple(item[4]),
        )
        for item in scored[:max_items]
    ]
