from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import settings
from app.services.product_taxonomy import infer_tags

logger = structlog.get_logger(__name__)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
IMAGE_PATH_HINTS = ("/api/media/", "/media/")


def is_likely_image_url(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in IMAGE_EXTS):
        return True
    if any(hint in path for hint in IMAGE_PATH_HINTS):
        return True
    return False


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_str_list(value: Any, limit: int = 8) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        for part in parts:
            if part and part.lower() != "unknown" and part not in items:
                items.append(part)
    elif isinstance(value, list):
        for entry in value:
            text = _coerce_str(entry)
            if text and text.lower() != "unknown" and text not in items:
                items.append(text)
    return items[:limit]


def _parse_json_response(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    if not cleaned.startswith("{"):
        return None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _build_analysis_text(summary: str, attrs: dict[str, str], search_terms: list[str]) -> str:
    parts = [summary]
    for key in ("category", "gender", "style", "material", "color", "brand"):
        value = attrs.get(key)
        if value:
            parts.append(value)
    parts.extend(search_terms[:6])
    return " ".join(part for part in parts if part).strip()


async def analyze_image_url(url: str, text_hint: str | None = None) -> dict[str, Any] | None:
    if not settings.VISION_ENABLED:
        return None
    provider = settings.VISION_PROVIDER.lower().strip()
    if provider != "openai":
        return None
    if not settings.OPENAI_API_KEY:
        return None

    system_prompt = (
        "Analyze ecommerce product images for product search.\n"
        "Reply with JSON only and this exact schema:\n"
        "{summary, category, gender, style, material, color, brand, notes, search_terms}.\n"
        "- summary: short Persian description.\n"
        "- search_terms: array of 3-8 short terms useful for finding this product in catalog.\n"
        "- Use 'unknown' when unsure. No markdown."
    )
    user_text = "Describe the product in the image in Persian."
    if text_hint:
        user_text += f" User hint: {text_hint}"

    payload = {
        "model": settings.VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            },
        ],
        "temperature": settings.VISION_TEMPERATURE,
    }
    if settings.VISION_MAX_TOKENS > 0:
        payload["max_tokens"] = settings.VISION_MAX_TOKENS

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    url_endpoint = f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=settings.VISION_TIMEOUT_SEC) as client:
            response = await client.post(url_endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("vision_failed", error=str(exc))
        return None

    choices = data.get("choices") or []
    content = ""
    if choices:
        content = choices[0].get("message", {}).get("content") or ""
    parsed = _parse_json_response(content)
    attrs: dict[str, str] = {}
    summary = ""
    notes = ""
    search_terms: list[str] = []
    if parsed:
        summary = _coerce_str(parsed.get("summary"))
        notes = _coerce_str(parsed.get("notes"))
        for key in ("category", "gender", "style", "material", "color", "brand"):
            value = _coerce_str(parsed.get(key))
            if value and value.lower() != "unknown":
                attrs[key] = value
        search_terms = _coerce_str_list(parsed.get("search_terms"))
    else:
        summary = _coerce_str(content)

    analysis_text = _build_analysis_text(summary, attrs, search_terms)
    tags = infer_tags(analysis_text)

    return {
        "summary": summary,
        "attributes": attrs,
        "notes": notes,
        "search_terms": search_terms,
        "analysis_text": analysis_text,
        "tags": {
            "categories": list(tags.categories),
            "genders": list(tags.genders),
            "styles": list(tags.styles),
            "materials": list(tags.materials),
            "colors": list(tags.colors),
            "sizes": list(tags.sizes),
        },
        "provider": provider,
    }
