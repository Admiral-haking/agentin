from __future__ import annotations

import asyncio
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

import httpx
import structlog
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.product import Product, ProductAvailability
from app.models.product_sync_run import ProductSyncRun
from app.services.app_log_store import log_event
from app.utils.time import utc_now

logger = structlog.get_logger(__name__)


@dataclass
class TorobProduct:
    product_id: str | None
    page_url: str
    price: int | None
    old_price: int | None
    availability: ProductAvailability


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
    source_flags: dict[str, bool]
    should_scrape: bool = False


_CACHE: dict[str, tuple[float, Any]] = {}
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

class _ProductHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.description: str | None = None
        self.images: list[str] = []
        self._capture_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "title":
            self._capture_title = True
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
        if prop in {"og:image", "twitter:image"}:
            if content and content not in self.images:
                self.images.append(content)

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


def _normalize_images(value: Any) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items.append(value)
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                items.append(entry)
            elif isinstance(entry, dict):
                url = entry.get("url") or entry.get("@id")
                if isinstance(url, str):
                    items.append(url)
    elif isinstance(value, dict):
        url = value.get("url") or value.get("@id")
        if isinstance(url, str):
            items.append(url)
    return [item.strip() for item in items if item and item.strip()]


def _merge_image_lists(
    existing: list[str] | None, incoming: list[str] | None
) -> list[str] | None:
    merged: list[str] = []
    for entry in (existing or []) + (incoming or []):
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
        parser = _ProductHTMLParser()
        parser.feed(html_text)
        title = parser.title
        description = parser.description
        images = parser.images or []
        images = _normalize_images(images)
        price: int | None = None
        availability: ProductAvailability | None = None
        json_ld = _extract_product_from_json_ld(html_text)
        if json_ld:
            title = json_ld.get("name") or json_ld.get("headline") or title
            description = json_ld.get("description") or description
            json_images = _normalize_images(json_ld.get("image") or json_ld.get("images"))
            images = _merge_image_lists(images, json_images) or []

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

        images = _merge_image_lists(images, None)
        return {
            "title": title,
            "description": description,
            "images": images,
            "price": price,
            "availability": availability,
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
        torob_products: list[TorobProduct] = []
        sitemap_entries: list[SitemapEntry] = []
        status_by_url: dict[str, str] = {}

        try:
            timeout = httpx.Timeout(settings.PRODUCT_SYNC_TIMEOUT_SEC)
            headers = {"User-Agent": "agentin-product-sync/1.0"}
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:
                torob_products, sitemap_entries = await asyncio.gather(
                    fetch_torob_products(client), fetch_sitemap_urls(client)
                )

            merged: dict[str, MergedProduct] = {}
            for item in torob_products:
                merged[item.page_url] = MergedProduct(
                    page_url=item.page_url,
                    slug=_extract_slug(item.page_url),
                    lastmod=None,
                    product_id=item.product_id,
                    price=item.price,
                    old_price=item.old_price,
                    availability=item.availability,
                    source_flags={"torob": True, "sitemap": False, "scraped": False},
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
                    source_flags={"torob": False, "sitemap": True, "scraped": False},
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
                    needs_scrape = not product.title
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
                        title=None,
                        description=None,
                        images=None,
                        price=entry.price,
                        old_price=entry.old_price,
                        availability=entry.availability,
                        lastmod=entry.lastmod,
                        source_flags=entry.source_flags,
                    )
                    entry.should_scrape = True
                    session.add(record)
                    existing_products[entry.page_url] = record
                    status_by_url[entry.page_url] = "created"
                    scrape_candidates.append((record, entry))

            await session.commit()

            if settings.PRODUCT_SCRAPE_ENABLED and scrape_candidates:
                semaphore = asyncio.Semaphore(settings.PRODUCT_SCRAPE_CONCURRENCY)
                scrape_limit = settings.PRODUCT_SCRAPE_MAX
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
            run.torob_count = len(torob_products)
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
                    "created": created_count,
                    "updated": updated_count,
                    "unchanged": unchanged_count,
                    "errors": error_count,
                },
                commit=False,
            )
            await session.commit()
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
