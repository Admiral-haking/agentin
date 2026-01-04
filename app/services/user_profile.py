from __future__ import annotations

import re
from typing import Any

from app.services.product_taxonomy import (
    COLOR_KEYWORDS,
    GENDER_SYNONYMS,
    SIZE_KEYWORDS,
    infer_tags,
)


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _parse_amount(token: str) -> int | None:
    digits = re.findall(r"\d+", token)
    if not digits:
        return None
    value = int("".join(digits))
    if "میلیون" in token:
        value *= 1_000_000
    elif "هزار" in token:
        value *= 1_000
    return value


def _extract_budget(text: str) -> dict[str, int]:
    results: dict[str, int] = {}
    tokens = re.split(r"\s+", text)
    amounts = [_parse_amount(token) for token in tokens]
    amounts = [amount for amount in amounts if amount]
    if not amounts:
        return results
    if "تا" in text or "بین" in text:
        if len(amounts) >= 2:
            results["budget_min"] = min(amounts[0], amounts[1])
            results["budget_max"] = max(amounts[0], amounts[1])
            return results
    if "زیر" in text or "کمتر" in text:
        results["budget_max"] = max(amounts)
        return results
    if "بالا" in text or "بیشتر" in text:
        results["budget_min"] = max(amounts)
        return results
    if len(amounts) == 1:
        results["budget_max"] = amounts[0]
    return results


def extract_preferences(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    normalized = _normalize_text(text)
    updates: dict[str, Any] = {}

    budget = _extract_budget(normalized)
    updates.update(budget)

    colors = [color for color in COLOR_KEYWORDS if color in normalized]
    if colors:
        updates["colors"] = list(dict.fromkeys(colors))

    size_match = re.search(r"سایز\s*([\w\-]+)", normalized)
    sizes = []
    if size_match:
        sizes.append(size_match.group(1))
    for item in SIZE_KEYWORDS:
        if item in normalized:
            sizes.append(item)
    sizes = [size for size in sizes if size]
    if sizes:
        updates["sizes"] = list(dict.fromkeys(sizes))

    for gender, keywords in GENDER_SYNONYMS.items():
        if any(keyword in normalized for keyword in keywords):
            updates["gender"] = gender
            break

    tags = infer_tags(normalized)
    if tags.sizes:
        sizes = list(dict.fromkeys(sizes + list(tags.sizes)))
    if sizes:
        updates["sizes"] = list(dict.fromkeys(sizes))
    if tags.categories:
        updates["categories"] = list(tags.categories)
    if tags.styles:
        updates["styles"] = list(tags.styles)
    if tags.materials:
        updates["materials"] = list(tags.materials)

    return updates
