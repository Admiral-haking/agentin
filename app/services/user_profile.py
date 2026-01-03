from __future__ import annotations

import re
from typing import Any


_COLOR_KEYWORDS = {
    "مشکی",
    "سفید",
    "قرمز",
    "آبی",
    "سبز",
    "زرد",
    "صورتی",
    "نارنجی",
    "سرمه‌ای",
    "سرمه اي",
    "طوسی",
    "خاکستری",
    "کرم",
    "قهوه‌ای",
    "قهوه اي",
    "بنفش",
    "طلایی",
    "طلائي",
    "نقره‌ای",
    "نقره اي",
}
_SIZE_KEYWORDS = {
    "xs",
    "s",
    "m",
    "l",
    "xl",
    "xxl",
    "xxxl",
    "فری",
    "فری‌سایز",
    "فری سایز",
    "free",
}
_GENDER_KEYWORDS = {
    "زنانه": "زنانه",
    "مردانه": "مردانه",
    "دخترانه": "زنانه",
    "پسرانه": "مردانه",
    "بچگانه": "بچگانه",
    "کودک": "بچگانه",
}
_CATEGORY_KEYWORDS = {
    "کفش": "کفش",
    "کتونی": "کفش",
    "اسنیکر": "کفش",
    "لباس": "لباس",
    "پیراهن": "لباس",
    "تی‌شرت": "لباس",
    "تیشرت": "لباس",
    "شلوار": "لباس",
    "هودی": "لباس",
    "مانتو": "لباس",
    "کیف": "کیف",
    "کوله": "کیف",
    "عطر": "عطر",
    "ادکلن": "عطر",
    "بادی": "عطر",
    "زیور": "زیورآلات",
    "گردنبند": "زیورآلات",
    "گوشواره": "زیورآلات",
    "دستبند": "زیورآلات",
    "آرایشی": "آرایشی",
    "بهداشتی": "بهداشتی",
    "کرم": "آرایشی",
    "رژ": "آرایشی",
    "ریمل": "آرایشی",
}


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

    colors = [color for color in _COLOR_KEYWORDS if color in normalized]
    if colors:
        updates["colors"] = list(dict.fromkeys(colors))

    size_match = re.search(r"سایز\s*([\w\-]+)", normalized)
    sizes = []
    if size_match:
        sizes.append(size_match.group(1))
    for item in _SIZE_KEYWORDS:
        if item in normalized:
            sizes.append(item)
    sizes = [size for size in sizes if size]
    if sizes:
        updates["sizes"] = list(dict.fromkeys(sizes))

    for key, value in _GENDER_KEYWORDS.items():
        if key in normalized:
            updates["gender"] = value
            break

    categories = []
    for key, value in _CATEGORY_KEYWORDS.items():
        if key in normalized:
            categories.append(value)
    if categories:
        updates["categories"] = list(dict.fromkeys(categories))

    return updates
