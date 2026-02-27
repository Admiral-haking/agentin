from __future__ import annotations

import asyncio
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bson import ObjectId
from pymongo import MongoClient
import structlog
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.product import Product, ProductAvailability
from app.models.product_sync_run import ProductSyncRun
from app.services.app_log_store import log_event
from app.services.product_catalog import refresh_catalog_snapshot
from app.utils.time import utc_now

logger = structlog.get_logger(__name__)


@dataclass
class TorobProduct:
    product_id: str | None
    page_url: str
    price: int | None
    old_price: int | None
    availability: ProductAvailability
    title: str | None = None
    description: str | None = None
    images: list[str] | None = None
    lastmod: datetime | None = None


@dataclass
class SitemapEntry:
    page_url: str
    lastmod: datetime | None


@dataclass
class MergedProduct:
    page_url: str
    slug: str | None
    lastmod: datetime | None
    product_id: str | None
    price: int | None
    old_price: int | None
    availability: ProductAvailability
    title: str | None
    description: str | None
    images: list[str] | None
    source_flags: dict[str, bool]
    should_scrape: bool = False


_CACHE: dict[str, tuple[float, Any]] = {}
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".avif",
    ".svg",
)

def _normalize_image_url(base_url: str, value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().strip('"').strip("'")
    cleaned = cleaned.rstrip("\\>,)")
    if not cleaned or cleaned.startswith("data:"):
        return None
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    resolved = urljoin(base_url, cleaned)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"}:
        return None
    return resolved


def _extract_srcset_urls(value: str | None) -> list[str]:
    if not value:
        return []
    urls: list[str] = []
    for part in value.split(","):
        url = part.strip().split(" ")[0]
        if url:
            urls.append(url)
    return urls


class _ProductHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title: str | None = None
        self.description: str | None = None
        self.images: list[str] = []
        self._capture_title = False
        self._title_parts: list[str] = []

    def _add_image(self, raw: str | None) -> None:
        url = _normalize_image_url(self.base_url, raw)
        if url and url not in self.images:
            self.images.append(url)

    def _add_srcset(self, raw: str | None) -> None:
        for candidate in _extract_srcset_urls(raw):
            self._add_image(candidate)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "title":
            self._capture_title = True
            return
        if tag.lower() == "img":
            self._add_image(attrs_dict.get("src"))
            self._add_image(attrs_dict.get("data-src"))
            self._add_image(attrs_dict.get("data-original"))
            self._add_image(attrs_dict.get("data-lazy"))
            self._add_image(attrs_dict.get("data-lazy-src"))
            self._add_srcset(attrs_dict.get("srcset"))
            self._add_srcset(attrs_dict.get("data-srcset"))
            return
        if tag.lower() == "source":
            self._add_srcset(attrs_dict.get("srcset"))
            self._add_srcset(attrs_dict.get("data-srcset"))
            return
        if tag.lower() == "link":
            rel = attrs_dict.get("rel", "").lower()
            if rel in {"image_src", "preload"}:
                self._add_image(attrs_dict.get("href"))
            return
        if tag.lower() != "meta":
            return
        prop = attrs_dict.get("property") or attrs_dict.get("name")
        content = attrs_dict.get("content")
        if not prop or not content:
            return
        prop = prop.strip().lower()
        content = html.unescape(content.strip())
        if prop in {"og:title", "twitter:title"} and not self.title:
            self.title = content
        if prop in {"og:description", "description"} and not self.description:
            self.description = content
        if prop in {"og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"}:
            self._add_image(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title" and self._capture_title:
            joined = "".join(self._title_parts).strip()
            if joined and not self.title:
                self.title = html.unescape(joined)
            self._capture_title = False
            self._title_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._title_parts.append(data)


def _cache_get(key: str, ttl: int) -> Any | None:
    cached = _CACHE.get(key)
    if not cached:
        return None
    ts, data = cached
    if time.monotonic() - ts > ttl:
        return None
    return data


def _cache_set(key: str, data: Any) -> None:
    _CACHE[key] = (time.monotonic(), data)


def _iter_json_ld_objects(raw: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        if "@graph" in raw and isinstance(raw["@graph"], list):
            for entry in raw["@graph"]:
                if isinstance(entry, dict):
                    items.append(entry)
        else:
            items.append(raw)
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                items.append(entry)
    return items


def _extract_product_from_json_ld(html_text: str) -> dict[str, Any] | None:
    for payload in _JSON_LD_RE.findall(html_text):
        cleaned = html.unescape(payload.strip())
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        for entry in _iter_json_ld_objects(data):
            raw_type = entry.get("@type")
            types = [raw_type] if isinstance(raw_type, str) else raw_type or []
            if isinstance(types, str):
                types = [types]
            if any(str(item).lower() == "product" for item in types):
                return entry
    return None


def _normalize_schema_availability(value: Any) -> ProductAvailability | None:
    if not value:
        return None
    if isinstance(value, str):
        lowered = value.lower()
        if "instock" in lowered:
            return ProductAvailability.instock
        if "outofstock" in lowered:
            return ProductAvailability.outofstock
    return None


def _infer_availability_from_html(html_text: str) -> ProductAvailability | None:
    lowered = html_text.lower()
    out_terms = [
        "ناموجود",
        "اتمام موجودی",
        "موجود نیست",
        "out of stock",
        "sold out",
        "unavailable",
    ]
    in_terms = [
        "موجود",
        "در انبار",
        "in stock",
        "available",
    ]
    if any(term in lowered for term in out_terms):
        return ProductAvailability.outofstock
    if any(term in lowered for term in in_terms):
        return ProductAvailability.instock
    return None


def _normalize_images(value: Any, base_url: str | None = None) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items.append(value)
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                items.append(entry)
            elif isinstance(entry, dict):
                for key in ("url", "contentUrl", "src", "@id"):
                    url = entry.get(key)
                    if isinstance(url, str):
                        items.append(url)
                nested = entry.get("image") or entry.get("images")
                items.extend(_normalize_images(nested))
    elif isinstance(value, dict):
        for key in ("url", "contentUrl", "src", "@id"):
            url = value.get(key)
            if isinstance(url, str):
                items.append(url)
        nested = value.get("image") or value.get("images")
        items.extend(_normalize_images(nested))
    cleaned: list[str] = []
    for item in items:
        candidate = item.strip() if item else ""
        if not candidate:
            continue
        if base_url:
            normalized = _normalize_image_url(base_url, candidate)
            if normalized:
                cleaned.append(normalized)
        else:
            cleaned.append(candidate)
    return cleaned


def _merge_image_lists(
    existing: Any, incoming: Any
) -> list[str] | None:
    merged: list[str] = []
    existing_items = _normalize_images(existing)
    incoming_items = _normalize_images(incoming)
    for entry in existing_items + incoming_items:
        entry = entry.strip() if entry else ""
        if entry and entry not in merged:
            merged.append(entry)
    return merged or None


def _iter_offer_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("@type") == "AggregateOffer" and value.get("offers"):
            return _iter_offer_objects(value.get("offers"))
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _extract_model_id(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("sku", "mpn", "model", "name", "value"):
            candidate = _extract_model_id(value.get(key))
            if candidate:
                return candidate
        return None
    if isinstance(value, list):
        for entry in value:
            candidate = _extract_model_id(entry)
            if candidate:
                return candidate
    return None


def _normalize_page_url(value: str) -> str:
    parsed = urlparse(value.strip())
    parsed = parsed._replace(query="", fragment="")
    normalized = urlunparse(parsed)
    if normalized.endswith("/") and len(normalized) > len(parsed.scheme) + 3:
        normalized = normalized.rstrip("/")
    return normalized


def _extract_slug(page_url: str) -> str | None:
    path = urlparse(page_url).path.rstrip("/")
    if "/product/" in path:
        return path.split("/product/")[-1] or None
    if not path:
        return None
    return path.split("/")[-1] or None


def _parse_lastmod(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _parse_price(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = re.findall(r"\d+", value)
        if not digits:
            return None
        return int("".join(digits))
    return None


def _normalize_availability(value: Any) -> ProductAvailability:
    if value is None:
        return ProductAvailability.unknown
    if isinstance(value, bool):
        return ProductAvailability.instock if value else ProductAvailability.outofstock
    if isinstance(value, (int, float)):
        return ProductAvailability.instock if value else ProductAvailability.outofstock
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"instock", "in_stock", "available", "yes", "true", "1"}:
            return ProductAvailability.instock
        if lowered in {"outofstock", "out_of_stock", "unavailable", "no", "false", "0"}:
            return ProductAvailability.outofstock
    return ProductAvailability.unknown


def _parse_mongo_query(value: str | None) -> dict[str, Any]:
    if not value:
        return {"status": "active"}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("MONGO_PRODUCTS_QUERY must be valid JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("MONGO_PRODUCTS_QUERY must be a JSON object")
    return payload


def _mongo_db_name(uri: str) -> str | None:
    parsed = urlparse(uri)
    path = (parsed.path or "").strip("/")
    return path or None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        return value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = f"{cleaned[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _resolve_page_base_url() -> str:
    explicit = (settings.MONGO_PRODUCTS_PAGE_BASE_URL or "").strip()
    if explicit:
        return explicit.rstrip("/")
    parsed = urlparse(settings.SITEMAP_URL or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://ghlbedovom.com"


def _to_clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _to_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and ObjectId.is_valid(candidate):
            return ObjectId(candidate)
    return None


def _object_id_str(value: Any) -> str | None:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate
    return None


def _iter_mongo_media_ids(doc: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    variants = doc.get("variants")
    if not isinstance(variants, list):
        return ids
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        media_ids = variant.get("mediaIds")
        if not isinstance(media_ids, list):
            continue
        for media_id in media_ids:
            as_str = _object_id_str(media_id)
            if as_str and as_str not in ids:
                ids.append(as_str)
    return ids


def _iter_mongo_category_ids(doc: dict[str, Any]) -> list[str]:
    categories = doc.get("categories")
    if not isinstance(categories, list):
        return []
    ids: list[str] = []
    for category_id in categories:
        as_str = _object_id_str(category_id)
        if as_str and as_str not in ids:
            ids.append(as_str)
    return ids


def _load_category_name_index(db: Any, category_ids: set[str]) -> dict[str, str]:
    if not category_ids:
        return {}
    object_ids: list[ObjectId] = []
    for value in sorted(category_ids):
        parsed = _to_object_id(value)
        if parsed is not None:
            object_ids.append(parsed)
    if not object_ids:
        return {}
    index: dict[str, str] = {}
    cursor = db["categories"].find(
        {"_id": {"$in": object_ids}},
        {"name": 1, "slug": 1},
    )
    for item in cursor:
        if not isinstance(item, dict):
            continue
        key = _object_id_str(item.get("_id"))
        if not key:
            continue
        name = _to_clean_text(item.get("name")) or _to_clean_text(item.get("slug"))
        if name:
            index[key] = name
    return index


def _load_media_file_index(db: Any, media_ids: set[str]) -> dict[str, str]:
    if not media_ids:
        return {}
    object_ids: list[ObjectId] = []
    for value in sorted(media_ids):
        parsed = _to_object_id(value)
        if parsed is not None:
            object_ids.append(parsed)
    if not object_ids:
        return {}
    index: dict[str, str] = {}
    cursor = db["media"].find(
        {"_id": {"$in": object_ids}},
        {"thumbId": 1, "mobileId": 1, "originalId": 1},
    )
    for item in cursor:
        if not isinstance(item, dict):
            continue
        key = _object_id_str(item.get("_id"))
        if not key:
            continue
        for field in ("thumbId", "mobileId", "originalId"):
            file_id = _object_id_str(item.get(field))
            if file_id:
                index[key] = file_id
                break
    return index


def _media_url(base_url: str, file_id: str) -> str:
    return f"{base_url}/api/media/{file_id}"


def _is_likely_product_image_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    path = (parsed.path or "").lower()
    if "/api/media/" in path or "/media/" in path or "/images/" in path or "/image/" in path:
        return True
    return any(path.endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _resolve_mongo_images(
    doc: dict[str, Any],
    *,
    page_base_url: str,
    media_file_index: dict[str, str],
) -> list[str] | None:
    resolved: list[str] = []
    for value in (
        doc.get("images"),
        doc.get("image"),
        doc.get("gallery"),
    ):
        for image_url in _normalize_images(value, base_url=page_base_url):
            if _is_likely_product_image_url(image_url) and image_url not in resolved:
                resolved.append(image_url)

    variants = doc.get("variants")
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            for image_url in _normalize_images(
                variant.get("images"), base_url=page_base_url
            ):
                if _is_likely_product_image_url(image_url) and image_url not in resolved:
                    resolved.append(image_url)
            media_ids = variant.get("mediaIds")
            if not isinstance(media_ids, list):
                continue
            for media_id in media_ids:
                media_key = _object_id_str(media_id)
                if not media_key:
                    continue
                file_id = media_file_index.get(media_key)
                if not file_id:
                    continue
                image_url = _media_url(page_base_url, file_id)
                if _is_likely_product_image_url(image_url) and image_url not in resolved:
                    resolved.append(image_url)

    return resolved or None


def _resolve_mongo_category_names(
    doc: dict[str, Any],
    category_name_index: dict[str, str],
) -> list[str]:
    names: list[str] = []
    for category_id in _iter_mongo_category_ids(doc):
        name = category_name_index.get(category_id)
        if name and name not in names:
            names.append(name)
    return names


def _format_attrs(attrs: Any) -> list[str]:
    if not isinstance(attrs, dict):
        return []
    chunks: list[str] = []
    for key, raw_value in attrs.items():
        if not isinstance(key, str):
            continue
        clean_key = key.strip()
        if not clean_key:
            continue
        if isinstance(raw_value, list):
            values = [
                str(item).strip()
                for item in raw_value
                if isinstance(item, (str, int, float)) and str(item).strip()
            ]
            if values:
                chunks.append(f"{clean_key}: {', '.join(values[:4])}")
        elif isinstance(raw_value, (str, int, float)):
            value = str(raw_value).strip()
            if value:
                chunks.append(f"{clean_key}: {value}")
    return chunks


def _format_attribute_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    chunks: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        key = _to_clean_text(item.get("key"))
        value = _to_clean_text(item.get("value"))
        if key and value:
            chunks.append(f"{key}: {value}")
    return chunks


def _build_mongo_description(
    doc: dict[str, Any],
    category_names: list[str],
) -> str | None:
    summary = (
        _to_clean_text(doc.get("description"))
        or _to_clean_text(doc.get("searchableText"))
        or None
    )
    meta_parts: list[str] = []
    brand = _to_clean_text(doc.get("brand"))
    if brand:
        meta_parts.append(f"برند: {brand}")
    if category_names:
        meta_parts.append(f"دسته‌بندی: {', '.join(category_names[:4])}")
    attr_chunks = _format_attrs(doc.get("attrs"))
    if attr_chunks:
        meta_parts.append("ویژگی‌ها: " + " | ".join(attr_chunks[:5]))
    attr_value_chunks = _format_attribute_values(doc.get("attributeValues"))
    if attr_value_chunks:
        meta_parts.append("جزئیات: " + " | ".join(attr_value_chunks[:5]))

    if not summary and not meta_parts:
        return None
    if summary and not meta_parts:
        return summary[:900]
    if meta_parts and not summary:
        return " | ".join(meta_parts)[:900]
    return f"{summary}\n{' | '.join(meta_parts)}"[:900]


def _price_snapshot_from_mongo_doc(
    doc: dict[str, Any],
    now: datetime | None = None,
) -> tuple[int | None, int | None, ProductAvailability]:
    now_utc = now or datetime.now(timezone.utc)
    variants = doc.get("variants")
    if not isinstance(variants, list):
        return None, None, ProductAvailability.unknown

    min_price: int | None = None
    min_old_price: int | None = None
    inventory_total = 0

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if variant.get("active") is False:
            continue

        price_model = variant.get("price")
        base_price = None
        if isinstance(price_model, dict):
            base_price = _parse_price(price_model.get("amount"))
        if base_price is None:
            continue

        final_price = base_price
        offer = variant.get("offer")
        if isinstance(offer, dict):
            discount = _parse_price(offer.get("amount")) or 0
            starts_at = _coerce_datetime(offer.get("startsAt"))
            ends_at = _coerce_datetime(offer.get("endsAt"))
            offer_active = (
                (starts_at is None or now_utc >= starts_at)
                and (ends_at is None or now_utc <= ends_at)
            )
            if offer_active and discount > 0:
                final_price = max(base_price - discount, 0)
                if final_price < base_price:
                    if min_old_price is None or base_price < min_old_price:
                        min_old_price = base_price

        if min_price is None or final_price < min_price:
            min_price = final_price

        inventory = variant.get("inventory")
        quantity = None
        if isinstance(inventory, dict):
            quantity = _parse_price(inventory.get("quantity"))
        if quantity and quantity > 0:
            inventory_total += quantity

    if min_price is None:
        availability = ProductAvailability.unknown
    elif inventory_total > 0:
        availability = ProductAvailability.instock
    else:
        availability = ProductAvailability.outofstock
    return min_price, min_old_price, availability


def _mongo_doc_to_product(
    doc: dict[str, Any],
    page_base_url: str,
    now: datetime | None = None,
    *,
    category_name_index: dict[str, str] | None = None,
    media_file_index: dict[str, str] | None = None,
) -> TorobProduct | None:
    slug = doc.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        return None
    normalized_slug = slug.strip().strip("/")
    page_url = _normalize_page_url(f"{page_base_url}/product/{normalized_slug}")
    price, old_price, availability = _price_snapshot_from_mongo_doc(doc, now=now)
    raw_id = doc.get("_id")
    product_id = str(raw_id) if raw_id is not None else None
    title = _to_clean_text(doc.get("title")) or _to_clean_text(doc.get("name"))
    categories = _resolve_mongo_category_names(doc, category_name_index or {})
    description = _build_mongo_description(doc, categories)
    images = _resolve_mongo_images(
        doc,
        page_base_url=page_base_url,
        media_file_index=media_file_index or {},
    )
    lastmod = _coerce_datetime(doc.get("updatedAt"))
    return TorobProduct(
        product_id=product_id,
        page_url=page_url,
        price=price,
        old_price=old_price,
        availability=availability,
        title=title,
        description=description,
        images=images,
        lastmod=lastmod,
    )


def _fetch_mongo_products_sync() -> list[TorobProduct]:
    uri = (settings.MONGO_PRODUCTS_URI or "").strip()
    if not uri:
        raise RuntimeError("MONGO_PRODUCTS_URI is not configured")
    db_name = (settings.MONGO_PRODUCTS_DB or "").strip() or _mongo_db_name(uri)
    if not db_name:
        raise RuntimeError("MONGO_PRODUCTS_DB is not configured and DB name was not found in URI")

    collection_name = (settings.MONGO_PRODUCTS_COLLECTION or "products").strip()
    if not collection_name:
        raise RuntimeError("MONGO_PRODUCTS_COLLECTION is not configured")

    query = _parse_mongo_query(settings.MONGO_PRODUCTS_QUERY)
    projection = {
        "_id": 1,
        "slug": 1,
        "status": 1,
        "title": 1,
        "name": 1,
        "description": 1,
        "searchableText": 1,
        "brand": 1,
        "attrs": 1,
        "attributeValues": 1,
        "categories": 1,
        "updatedAt": 1,
        "variants": 1,
    }

    page_base_url = _resolve_page_base_url()
    now_utc = datetime.now(timezone.utc)
    results: list[TorobProduct] = []
    limit = max(settings.MONGO_PRODUCTS_LIMIT, 0)

    with MongoClient(
        uri,
        serverSelectionTimeoutMS=settings.MONGO_PRODUCTS_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGO_PRODUCTS_SOCKET_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGO_PRODUCTS_CONNECT_TIMEOUT_MS,
    ) as client:
        cursor = client[db_name][collection_name].find(query, projection=projection)
        if limit > 0:
            cursor = cursor.limit(limit)
        docs = [doc for doc in cursor if isinstance(doc, dict)]

        category_ids: set[str] = set()
        media_ids: set[str] = set()
        for doc in docs:
            category_ids.update(_iter_mongo_category_ids(doc))
            media_ids.update(_iter_mongo_media_ids(doc))

        db = client[db_name]
        category_name_index = _load_category_name_index(db, category_ids)
        media_file_index = _load_media_file_index(db, media_ids)

        for doc in docs:
            mapped = _mongo_doc_to_product(
                doc,
                page_base_url,
                now=now_utc,
                category_name_index=category_name_index,
                media_file_index=media_file_index,
            )
            if mapped:
                results.append(mapped)
    return results


async def _get_with_retries(
    client: httpx.AsyncClient, url: str, *, expect_json: bool
) -> Any:
    last_exc: Exception | None = None
    retries = max(settings.PRODUCT_SYNC_RETRIES, 0) + 1
    for attempt in range(retries):
        try:
            response = await client.get(url)
            response.raise_for_status()
            if expect_json:
                return response.json()
            return response.text
        except Exception as exc:
            last_exc = exc
            await asyncio.sleep(0.4 * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected fetch failure")


async def fetch_torob_products(client: httpx.AsyncClient) -> list[TorobProduct]:
    cached = _cache_get("torob_products", settings.PRODUCT_SYNC_CACHE_TTL_SEC)
    if cached is not None:
        return cached
    data = await _get_with_retries(client, settings.TOROB_PRODUCTS_URL, expect_json=True)
    items: list[TorobProduct] = []
    for item in data.get("products", []):
        page_url = item.get("page_url")
        if not page_url:
            continue
        normalized = _normalize_page_url(str(page_url))
        if "/product/" not in urlparse(normalized).path:
            continue
        items.append(
            TorobProduct(
                product_id=str(item.get("product_id")) if item.get("product_id") else None,
                page_url=normalized,
                price=_parse_price(item.get("price")),
                old_price=_parse_price(item.get("old_price")),
                availability=_normalize_availability(item.get("availability")),
            )
        )
    _cache_set("torob_products", items)
    return items


async def fetch_mongo_products() -> list[TorobProduct]:
    cache_key = (
        "mongo_products:"
        f"{settings.MONGO_PRODUCTS_URI}|{settings.MONGO_PRODUCTS_DB}|"
        f"{settings.MONGO_PRODUCTS_COLLECTION}|{settings.MONGO_PRODUCTS_QUERY}|"
        f"{settings.MONGO_PRODUCTS_LIMIT}"
    )
    cached = _cache_get(cache_key, settings.PRODUCT_SYNC_CACHE_TTL_SEC)
    if cached is not None:
        return cached
    items = await asyncio.to_thread(_fetch_mongo_products_sync)
    _cache_set(cache_key, items)
    return items


async def fetch_sitemap_urls(client: httpx.AsyncClient) -> list[SitemapEntry]:
    cached = _cache_get("sitemap_urls", settings.PRODUCT_SYNC_CACHE_TTL_SEC)
    if cached is not None:
        return cached
    xml_text = await _get_with_retries(client, settings.SITEMAP_URL, expect_json=False)
    entries: list[SitemapEntry] = []
    root = html.unescape(xml_text)
    tree = None
    try:
        tree = ET.fromstring(root)
    except Exception:
        tree = None
    if tree is None:
        _cache_set("sitemap_urls", entries)
        return entries
    for url_node in tree.findall(".//{*}url"):
        loc = url_node.findtext("{*}loc")
        if not loc:
            continue
        normalized = _normalize_page_url(loc)
        if "/product/" not in urlparse(normalized).path:
            continue
        lastmod_text = url_node.findtext("{*}lastmod")
        entries.append(SitemapEntry(page_url=normalized, lastmod=_parse_lastmod(lastmod_text)))
    _cache_set("sitemap_urls", entries)
    return entries


async def _scrape_product(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    async with semaphore:
        if settings.PRODUCT_SCRAPE_DELAY_SEC:
            await asyncio.sleep(settings.PRODUCT_SCRAPE_DELAY_SEC)
        html_text = await _get_with_retries(client, url, expect_json=False)
        parser = _ProductHTMLParser(url)
        parser.feed(html_text)
        title = parser.title
        description = parser.description
        images = parser.images or []
        images = _normalize_images(images, url)
        price: int | None = None
        availability: ProductAvailability | None = None
        model_id: str | None = None
        json_ld = _extract_product_from_json_ld(html_text)
        if json_ld:
            title = json_ld.get("name") or json_ld.get("headline") or title
            description = json_ld.get("description") or description
            json_images = _normalize_images(
                json_ld.get("image") or json_ld.get("images"),
                url,
            )
            images = _merge_image_lists(images, json_images) or []
            model_id = _extract_model_id(
                json_ld.get("sku")
                or json_ld.get("mpn")
                or json_ld.get("model")
            )

            offers = json_ld.get("offers")
            for offer in _iter_offer_objects(offers):
                if price is None:
                    price = _parse_price(
                        offer.get("price")
                        or offer.get("lowPrice")
                        or offer.get("highPrice")
                    )
                if price is None:
                    price_spec = offer.get("priceSpecification")
                    if isinstance(price_spec, dict):
                        price = _parse_price(price_spec.get("price"))
                    elif isinstance(price_spec, list):
                        for spec in price_spec:
                            if isinstance(spec, dict):
                                price = _parse_price(spec.get("price"))
                                if price is not None:
                                    break
                if availability is None:
                    availability = _normalize_schema_availability(
                        offer.get("availability")
                    )
                if price is not None and availability is not None:
                    break
        if availability is None:
            availability = _infer_availability_from_html(html_text)

        images = _merge_image_lists(images, None)
        return {
            "title": title,
            "description": description,
            "images": images,
            "price": price,
            "availability": availability,
            "model_id": model_id,
        }


def _merge_flags(
    existing: dict[str, Any] | None, updates: dict[str, bool]
) -> dict[str, bool]:
    merged: dict[str, bool] = {}
    if existing:
        merged.update({str(k): bool(v) for k, v in existing.items()})
    for key, value in updates.items():
        merged[key] = bool(value)
    return merged


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def run_product_sync(run_id: int | None = None) -> None:
    async with AsyncSessionLocal() as session:
        run: ProductSyncRun | None = None
        if run_id:
            run = await session.get(ProductSyncRun, run_id)
        if not run:
            run = ProductSyncRun(status="running", started_at=utc_now(), error_count=0)
            session.add(run)
            await session.commit()

        await log_event(
            session,
            level="info",
            event_type="product_sync_started",
            data={"run_id": run.id},
            commit=False,
        )
        await session.commit()

        error_count = 0
        source_products: list[TorobProduct] = []
        sitemap_entries: list[SitemapEntry] = []
        status_by_url: dict[str, str] = {}
        sync_source = "mongo"

        try:
            timeout = httpx.Timeout(settings.PRODUCT_SYNC_TIMEOUT_SEC)
            headers = {"User-Agent": "agentin-product-sync/1.0"}
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:
                source_fetch = fetch_mongo_products()
                source_products, sitemap_entries = await asyncio.gather(
                    source_fetch,
                    fetch_sitemap_urls(client),
                )

            merged: dict[str, MergedProduct] = {}
            for item in source_products:
                base_flags = {
                    "mongo": True,
                    "torob": False,
                    "sitemap": False,
                    "scraped": False,
                }
                merged[item.page_url] = MergedProduct(
                    page_url=item.page_url,
                    slug=_extract_slug(item.page_url),
                    lastmod=item.lastmod,
                    product_id=item.product_id,
                    price=item.price,
                    old_price=item.old_price,
                    availability=item.availability,
                    title=item.title,
                    description=item.description,
                    images=item.images,
                    source_flags=base_flags,
                )

            for entry in sitemap_entries:
                existing = merged.get(entry.page_url)
                if existing:
                    existing.lastmod = entry.lastmod
                    existing.source_flags["sitemap"] = True
                    continue
                merged[entry.page_url] = MergedProduct(
                    page_url=entry.page_url,
                    slug=_extract_slug(entry.page_url),
                    lastmod=entry.lastmod,
                    product_id=None,
                    price=None,
                    old_price=None,
                    availability=ProductAvailability.unknown,
                    title=None,
                    description=None,
                    images=None,
                    source_flags={
                        "mongo": False,
                        "torob": False,
                        "sitemap": True,
                        "scraped": False,
                    },
                )

            page_urls = list(merged.keys())
            existing_products: dict[str, Product] = {}
            if page_urls:
                for chunk in _chunked(page_urls, 1000):
                    result = await session.execute(
                        select(Product).where(Product.page_url.in_(chunk))
                    )
                    existing_products.update(
                        {
                            product.page_url: product
                            for product in result.scalars().all()
                            if product.page_url
                        }
                    )

            scrape_candidates: list[tuple[Product, MergedProduct]] = []

            for entry in merged.values():
                product = existing_products.get(entry.page_url)
                if product:
                    effective_title = product.title or entry.title
                    effective_images = product.images or entry.images
                    effective_price = product.price if product.price is not None else entry.price
                    effective_availability = (
                        product.availability
                        if product.availability != ProductAvailability.unknown
                        else entry.availability
                    )

                    needs_scrape = not effective_title or not effective_images
                    if effective_availability == ProductAvailability.unknown:
                        needs_scrape = True
                    if effective_price is None:
                        needs_scrape = True
                    if entry.lastmod and product.lastmod and entry.lastmod > product.lastmod:
                        needs_scrape = True
                    entry.should_scrape = needs_scrape

                    changed = False
                    if entry.product_id and entry.product_id != product.product_id:
                        product.product_id = entry.product_id
                        changed = True
                    if entry.slug and entry.slug != product.slug:
                        product.slug = entry.slug
                        changed = True
                    if entry.title and entry.title != product.title:
                        product.title = entry.title
                        changed = True
                    if entry.description and entry.description != product.description:
                        product.description = entry.description
                        changed = True
                    if entry.price is not None and entry.price != product.price:
                        product.price = entry.price
                        changed = True
                    if entry.old_price is not None and entry.old_price != product.old_price:
                        product.old_price = entry.old_price
                        changed = True
                    if entry.availability != product.availability:
                        product.availability = entry.availability
                        changed = True
                    if entry.lastmod and (
                        not product.lastmod or entry.lastmod > product.lastmod
                    ):
                        product.lastmod = entry.lastmod
                        changed = True

                    merged_flags = _merge_flags(product.source_flags, entry.source_flags)
                    if merged_flags != (product.source_flags or {}):
                        product.source_flags = merged_flags
                        changed = True

                    normalized_images = _normalize_images(product.images)
                    if product.images and normalized_images != product.images:
                        product.images = normalized_images
                        changed = True
                    if entry.images:
                        merged_images = _merge_image_lists(entry.images, product.images)
                        if merged_images != product.images:
                            product.images = merged_images
                            changed = True

                    if entry.should_scrape:
                        scrape_candidates.append((product, entry))

                    if changed:
                        status_by_url[entry.page_url] = "updated"
                    else:
                        status_by_url.setdefault(entry.page_url, "unchanged")
                else:
                    record = Product(
                        product_id=entry.product_id,
                        slug=entry.slug,
                        page_url=entry.page_url,
                        title=entry.title,
                        description=entry.description,
                        images=entry.images,
                        price=entry.price,
                        old_price=entry.old_price,
                        availability=entry.availability,
                        lastmod=entry.lastmod,
                        source_flags=entry.source_flags,
                    )
                    entry.should_scrape = not (
                        entry.title
                        and entry.images
                        and entry.price is not None
                        and entry.availability != ProductAvailability.unknown
                    )
                    session.add(record)
                    existing_products[entry.page_url] = record
                    status_by_url[entry.page_url] = "created"
                    if entry.should_scrape:
                        scrape_candidates.append((record, entry))

            await session.commit()

            if settings.PRODUCT_SCRAPE_ENABLED and scrape_candidates:
                semaphore = asyncio.Semaphore(settings.PRODUCT_SCRAPE_CONCURRENCY)
                scrape_limit = settings.PRODUCT_SCRAPE_MAX
                if scrape_limit <= 0:
                    limited_candidates = scrape_candidates
                else:
                    limited_candidates = scrape_candidates[:scrape_limit]

                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=True,
                    headers=headers,
                ) as client:
                    tasks = []
                    for product, entry in limited_candidates:
                        tasks.append(
                            _scrape_product(client, entry.page_url, semaphore)
                        )

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                for (product, entry), result in zip(limited_candidates, results):
                    if isinstance(result, Exception):
                        error_count += 1
                        continue
                    title = result.get("title")
                    description = result.get("description")
                    images = result.get("images")
                    scraped_price = result.get("price")
                    scraped_availability = result.get("availability")
                    scraped_model = result.get("model_id")

                    changed = False
                    if title and title != product.title:
                        product.title = title
                        changed = True
                    if description and description != product.description:
                        product.description = description
                        changed = True
                    if images:
                        merged_images = _merge_image_lists(product.images, images)
                        if merged_images != product.images:
                            product.images = merged_images
                            changed = True
                    if scraped_price is not None and product.price is None:
                        product.price = scraped_price
                        changed = True
                    if (
                        scraped_availability is not None
                        and product.availability == ProductAvailability.unknown
                    ):
                        product.availability = scraped_availability
                        changed = True
                    if scraped_model and not product.product_id:
                        existing = await session.execute(
                            select(Product.id).where(Product.product_id == scraped_model)
                        )
                        if existing.scalars().first() is None:
                            product.product_id = scraped_model
                            changed = True
                    flags = _merge_flags(product.source_flags, {"scraped": True})
                    if flags != (product.source_flags or {}):
                        product.source_flags = flags
                        changed = True
                    if changed and status_by_url.get(entry.page_url) != "created":
                        status_by_url[entry.page_url] = "updated"
                await session.commit()

            created_count = sum(1 for status in status_by_url.values() if status == "created")
            updated_count = sum(1 for status in status_by_url.values() if status == "updated")
            unchanged_count = sum(1 for status in status_by_url.values() if status == "unchanged")

            run.status = "success"
            run.finished_at = utc_now()
            run.torob_count = len(source_products)
            run.sitemap_count = len(sitemap_entries)
            run.created_count = created_count
            run.updated_count = updated_count
            run.unchanged_count = unchanged_count
            run.error_count = error_count
            run.error_message = None
            await log_event(
                session,
                level="info",
                event_type="product_sync_finished",
                data={
                    "run_id": run.id,
                    "source": sync_source,
                    "created": created_count,
                    "updated": updated_count,
                    "unchanged": unchanged_count,
                    "errors": error_count,
                },
                commit=False,
            )
            await session.commit()
            try:
                await refresh_catalog_snapshot(session)
            except Exception as exc:
                logger.warning("catalog_snapshot_failed", error=str(exc))
        except Exception as exc:
            logger.exception("product_sync_failed", error=str(exc))
            run.status = "failed"
            run.finished_at = utc_now()
            run.error_count = (run.error_count or 0) + 1
            run.error_message = str(exc)[:1000]
            await log_event(
                session,
                level="error",
                event_type="product_sync_failed",
                message=str(exc),
                data={"run_id": run.id},
                commit=False,
            )
            await session.commit()
