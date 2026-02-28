from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import structlog
from sqlalchemy import Integer, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import (
    BotSettings,
    Campaign,
    Conversation,
    Faq,
    Message,
    AppLog,
    Product,
    Usage,
    User,
)
from app.schemas.send import OutboundPlan, QuickReplyOption
from app.schemas.webhook import NormalizedMessage
from app.knowledge.store import get_store_knowledge_text
from app.services.app_log_store import log_event
from app.services.guardrails import (
    build_branches_plan,
    build_contact_plan,
    build_decline_response,
    build_goodbye_response,
    build_hours_response,
    build_phone_response,
    build_product_details_question,
    build_rule_based_plan,
    build_thanks_response,
    build_trust_response,
    build_website_plan,
    format_outbound_text,
    fallback_for_message_type,
    is_decline,
    is_goodbye,
    is_greeting,
    is_negative_feedback,
    is_purchase_confirmation,
    is_thanks,
    needs_product_details,
    plan_outbound,
    post_process,
    validate_reply_or_rewrite,
    wants_product_intent,
    wants_product_address,
    wants_product_link,
    wants_address,
    wants_hours,
    wants_more_products,
    wants_phone,
    wants_repeat,
    wants_trust,
    wants_website,
    wants_contact,
)
from app.services.instagram_user_client import (
    InstagramUserClient,
    InstagramUserClientError,
)
from app.services.llm_clients import LLMError, generate_reply
from app.services.llm_router import choose_provider
from app.services.order_flow import handle_order_flow
from app.services.product_matcher import (
    match_products_with_scores,
    tokenize_query,
)
from app.services.admin_media_notes import (
    create_admin_media_note,
    format_admin_media_notes,
    get_recent_admin_media_notes,
)
from app.services.admin_policy_memory import (
    format_admin_policy_memory,
    get_admin_policy_memory,
    store_admin_policy_memory,
)
from app.services.product_catalog import get_catalog_snapshot
from app.services.behavior_analyzer import (
    analyze_user_behavior,
    BehaviorMatch,
)
from app.services.conversation_state import (
    build_state_payload,
    get_or_create_state,
    infer_category as infer_state_category,
    infer_intent as infer_state_intent,
    record_bot_action,
    update_state,
)
from app.services.cross_sell import find_cross_sell_product
from app.services.followups import cancel_followups_for_conversation, schedule_followup_task
from app.services.product_presenter import (
    build_category_links_plan,
    build_product_plan,
    build_product_url,
    build_selected_product_payload,
    wants_product_list,
)
from app.services.intent_router import route_intent
from app.services.product_taxonomy import infer_tags
from app.services.prompts import load_prompt
from app.services.media_analyzer import analyze_image_url, is_likely_image_url
from app.services.sender import Sender, SenderError
from app.services.support_tickets import (
    auto_escalate_loop_to_operator,
    get_or_create_ticket,
)
from app.services.user_behavior_store import (
    build_behavior_snapshot,
    get_behavior_profile,
    upsert_behavior_profile,
)
from app.services.user_profile import extract_preferences
from app.utils.time import parse_timestamp, utc_now

logger = structlog.get_logger(__name__)
SHOW_PRODUCTS_TOKEN = "[SHOW_PRODUCTS]"
SHOW_PRODUCTS_TOKEN_ALT = "[GENERIC_TEMPLATE]"
REQUIRED_FIELD_LABELS = {
    "gender": "جنسیت (آقایون/خانم‌ها/بچگانه)",
    "size": "سایز",
    "style": "سبک (رسمی/اسپرت)",
    "budget": "بازه قیمت",
    "color": "رنگ",
    "category": "دسته‌بندی محصول",
}
DEFAULT_REQUIRED_FIELDS = ["gender", "size", "style", "budget"]
SHOE_CATEGORIES = {"کفش", "صندل و دمپایی", "مجلسی و طبی"}
APPAREL_CATEGORIES = {"پوشاک", "لباس زیر", "شال و روسری", "کلاه و شال گردن"}
COSMETIC_CATEGORIES = {"آرایشی و بهداشتی", "آرایشی", "بهداشتی"}
PERFUME_CATEGORIES = {"عطر و ادکلن", "ادکلن", "بادی اسپلش", "اسپری"}
ACCESSORY_CATEGORIES = {"اکسسوری", "کیف", "جوراب", "لوازم جانبی"}
PRODUCT_URL_HOSTS = {"ghlbedovom.com"}
PRODUCT_URL_PREFIX = "/product/"
PRODUCT_URL_RE = re.compile(r"https?://[^\s)]+")
QUESTION_MARK_RE = re.compile(r"[؟?]")
REPEAT_CLEAN_RE = re.compile(r"[^\w\u0600-\u06FF ]+")
QUESTION_SENTENCE_RE = re.compile(r"[^؟?]*[؟?]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!؟?])\\s+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF]")
FOLLOWUP_PATTERNS = {
    "ready_to_buy",
    "price_inquiry",
    "availability_check",
    "comparison_request",
}
BOOT_KEYWORDS = {
    "بوت",
    "چکمه",
    "نیم بوت",
    "نیم‌بوت",
    "نیم‌ بوت",
    "boot",
    "boots",
}
_DIGIT_TRANSLATE = str.maketrans({
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
})
PRICE_VALUE_RE = re.compile(r"(?<!\d)\d{3,}(?:[,\u066C]\d{3})*(?!\d)")
PRICE_HINT_RE = re.compile(r"(قیمت|تومان|تومن|ریال|price)", re.IGNORECASE)
IMAGE_BLIND_REPLY_RE = re.compile(
    r"(نمی.?توانم|نمی.?تونم|متوجه نمی.?شم|can't|cannot).{0,24}(تصویر|عکس|image|photo)",
    re.IGNORECASE,
)
GENERIC_ASSISTANT_REPLY_RE = re.compile(
    r"(چطور می.?توانم.*کمک|سوالی درباره محصولات|به نظر می.?رسد که شما (عکسی|تصویری) ارسال کرده.?اید|برای معرفی دقیق.?تر)",
    re.IGNORECASE,
)


def _extract_product_slug(text: str | None) -> str | None:
    if not text:
        return None
    for match in PRODUCT_URL_RE.findall(text):
        cleaned = match.rstrip(").,")
        parsed = urlparse(cleaned)
        if parsed.netloc not in PRODUCT_URL_HOSTS:
            continue
        if PRODUCT_URL_PREFIX not in parsed.path:
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if "product" not in parts:
            continue
        idx = parts.index("product")
        if idx + 1 >= len(parts):
            continue
        slug = parts[idx + 1].strip()
        if slug:
            return slug
    return None


def _is_boot_request(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.replace("\u200c", " ").lower()
    return any(keyword in normalized for keyword in BOOT_KEYWORDS)


def _is_boot_product(product: Product) -> bool:
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
    return any(keyword in haystack for keyword in BOOT_KEYWORDS)


def _plan_to_text(plan: OutboundPlan) -> str:
    if plan.text:
        return plan.text
    if plan.type == "generic_template":
        lines = []
        for element in plan.elements:
            line = element.title
            if element.subtitle:
                line = f"{line} - {element.subtitle}"
            lines.append(line)
        if lines:
            return "\n".join(lines)
    return fallback_for_message_type("text")


def _build_more_products_plan() -> OutboundPlan:
    return OutboundPlan(
        type="quick_reply",
        text="اگر ادامه می‌خواهید بنویسید «ادامه».",
        quick_replies=[QuickReplyOption(title="ادامه", payload="ادامه")],
    )


def _limit_questions(text: str, max_questions: int) -> str:
    if not text:
        return text
    if max_questions < 0:
        return text
    parts = re.split(r"([؟?])", text)
    if len(parts) <= 1:
        return text
    result: list[str] = []
    question_count = 0
    for idx in range(0, len(parts), 2):
        sentence = parts[idx]
        mark = parts[idx + 1] if idx + 1 < len(parts) else ""
        if mark:
            question_count += 1
            if question_count <= max_questions:
                result.append(sentence + mark)
            else:
                if sentence.strip():
                    result.append(sentence.strip())
        else:
            result.append(sentence)
    cleaned = "".join(result).strip()
    return cleaned or text


def _normalize_repeat(text: str) -> str:
    cleaned = REPEAT_CLEAN_RE.sub(" ", text.lower())
    return " ".join(cleaned.split())


def _is_repetitive_reply(text: str, last_text: str | None) -> bool:
    if not text or not last_text:
        return False
    current = _normalize_repeat(text)
    previous = _normalize_repeat(last_text)
    if not current or not previous:
        return False
    if current == previous:
        return True
    if current in previous or previous in current:
        return len(current.split()) >= 4 and len(previous.split()) >= 4
    current_tokens = set(current.split())
    previous_tokens = set(previous.split())
    if not current_tokens or not previous_tokens:
        return False
    overlap = len(current_tokens & previous_tokens) / len(current_tokens | previous_tokens)
    return overlap >= 0.9 and len(current_tokens) >= 4


def _limit_sentences(text: str, max_sentences: int) -> str:
    if not text or max_sentences <= 0:
        return text
    parts = SENTENCE_SPLIT_RE.split(text.strip())
    if len(parts) <= max_sentences:
        return text
    return " ".join(parts[:max_sentences]).strip()


def _limit_emojis(text: str, max_emojis: int) -> str:
    if not text or max_emojis < 0:
        return text
    count = 0
    output: list[str] = []
    for ch in text:
        if EMOJI_RE.match(ch):
            count += 1
            if count > max_emojis:
                continue
        output.append(ch)
    return "".join(output)


def _normalize_digits(text: str) -> str:
    return (text or "").translate(_DIGIT_TRANSLATE)


def _extract_price_values(text: str | None) -> set[int]:
    if not text:
        return set()
    normalized = _normalize_digits(text)
    if not PRICE_HINT_RE.search(normalized):
        return set()
    values: set[int] = set()
    for token in PRICE_VALUE_RE.findall(normalized):
        try:
            values.add(int(token.replace(",", "").replace("\u066C", "")))
        except ValueError:
            continue
    return values


def _allowed_price_values(
    products: list[Product] | None,
    selected_product: dict[str, Any] | None,
) -> set[int]:
    values: set[int] = set()
    for product in products or []:
        if isinstance(product.price, int) and product.price > 0:
            values.add(product.price)
        if isinstance(product.old_price, int) and product.old_price > 0:
            values.add(product.old_price)
    if isinstance(selected_product, dict):
        for key in ("price", "old_price"):
            raw = selected_product.get(key)
            if isinstance(raw, int) and raw > 0:
                values.add(raw)
    return values


def _price_is_grounded(value: int, allowed_values: set[int]) -> bool:
    if value in allowed_values:
        return True
    # Accept common تومان/ریال mismatch.
    if value * 10 in allowed_values or (value % 10 == 0 and value // 10 in allowed_values):
        return True
    return False


def _reply_has_ungrounded_price(
    reply_text: str | None,
    allowed_values: set[int],
) -> bool:
    mentioned = _extract_price_values(reply_text)
    if not mentioned:
        return False
    if not allowed_values:
        return True
    return any(not _price_is_grounded(value, allowed_values) for value in mentioned)


def _looks_like_image_blind_reply(text: str | None) -> bool:
    if not text:
        return False
    normalized = " ".join(text.split())
    if not normalized:
        return False
    return bool(IMAGE_BLIND_REPLY_RE.search(normalized))


def _looks_like_generic_assistant_reply(text: str | None) -> bool:
    if not text:
        return False
    normalized = " ".join(text.split())
    if len(normalized) < 24:
        return False
    return bool(GENERIC_ASSISTANT_REPLY_RE.search(normalized))


def _display_name(user: User | None) -> str | None:
    if not user or not user.username:
        return None
    cleaned = user.username.strip().lstrip("@")
    if not cleaned:
        return None
    if "_" in cleaned:
        cleaned = cleaned.split("_", 1)[0].strip()
    if "." in cleaned and len(cleaned) > 10:
        cleaned = cleaned.split(".", 1)[0].strip()
    if not cleaned:
        return None
    return cleaned[:18]


def _format_price_label(value: int | None) -> str:
    if isinstance(value, int) and value > 0:
        return f"{value:,} تومان"
    return "قیمت نامشخص"


def _build_contextual_reply(
    *,
    user: User | None,
    query_text: str | None,
    analysis_text: str | None,
    matched_products: list[Product] | None,
    wants_products: bool,
    needs_details: bool,
) -> str:
    name = _display_name(user)
    prefix = f"{name} جان، " if name else ""
    products = matched_products or []
    if products:
        top = products[0]
        title = (top.title or top.slug or "این مدل").strip()
        price_text = _format_price_label(top.price)
        if wants_products or len(products) > 1:
            return (
                f"{prefix}چند گزینه نزدیک پیدا شد و الان کارت محصولات رو می‌فرستم. "
                "اگه سایز/رنگ دقیق بدی، فیلترش می‌کنم."
            )
        if needs_details:
            return f"{prefix}{title} موجوده ({price_text}). سایز یا رنگ مدنظرتون رو بگید تا دقیق‌تر چک کنم."
        return f"{prefix}{title} موجوده ({price_text}). اگر مدل مشابه می‌خواید بگید تا چند گزینه دیگه هم بفرستم."
    if analysis_text:
        summary = " ".join(analysis_text.split())
        if len(summary) > 100:
            summary = summary[:100].rstrip() + "..."
        return (
            f"{prefix}عکس رو بررسی کردم ({summary}). "
            "برای اعلام قیمت دقیق، لطفاً سایز یا رنگ مدنظرتون رو هم بفرستید."
        )
    normalized_query = " ".join((query_text or "").split())
    if normalized_query:
        return (
            f"{prefix}برای پیشنهاد دقیق، لطفاً یکی از این‌ها رو مشخص کنید: "
            "مدل، بازه قیمت، یا رنگ/سایز مدنظر."
        )
    return (
        f"{prefix}برای راهنمایی دقیق‌تر، اسم مدل یا عکس محصول رو بفرستید تا از روی موجودی سایت پیشنهاد بدم."
    )


def _build_personalized_greeting(user: User | None) -> str:
    name = _display_name(user)
    salutation = f"سلام {name} جان 🌷" if name else "سلام 🌷"
    if user and user.is_vip:
        return f"{salutation} خوش اومدی. برای انتخاب سریع، بگو دنبال چه مدل یا بازه قیمتی هستی؟"
    return f"{salutation} خوش اومدی به قلب دوم. دنبال چه مدل یا دسته‌ای هستی؟"


def _remember_user_context(
    profile_json: dict[str, Any] | None,
    *,
    user_text: str | None,
    matched_products: list[Product] | None,
    selected_product: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, bool]:
    original = profile_json if isinstance(profile_json, dict) else None
    profile = dict(original or {})
    memory = profile.get("memory")
    if not isinstance(memory, dict):
        memory = {}

    changed = False
    recent_queries = memory.get("recent_queries")
    if not isinstance(recent_queries, list):
        recent_queries = []
    normalized_query = " ".join((user_text or "").split())
    if normalized_query:
        normalized_query = normalized_query[:180]
        if not recent_queries or recent_queries[-1] != normalized_query:
            recent_queries.append(normalized_query)
            changed = True
        max_items = max(settings.USER_MEMORY_ITEMS, 1)
        if len(recent_queries) > max_items:
            recent_queries = recent_queries[-max_items:]
            changed = True

    recent_product_slugs = memory.get("recent_product_slugs")
    if not isinstance(recent_product_slugs, list):
        recent_product_slugs = []
    seen = {slug for slug in recent_product_slugs if isinstance(slug, str)}
    for product in (matched_products or [])[:3]:
        slug = (product.slug or "").strip()
        if slug and slug not in seen:
            recent_product_slugs.append(slug)
            seen.add(slug)
            changed = True
    if isinstance(selected_product, dict):
        slug = selected_product.get("slug")
        if isinstance(slug, str):
            slug = slug.strip()
            if slug and slug not in seen:
                recent_product_slugs.append(slug)
                seen.add(slug)
                changed = True
    max_items = max(settings.USER_MEMORY_ITEMS, 1)
    if len(recent_product_slugs) > max_items:
        recent_product_slugs = recent_product_slugs[-max_items:]
        changed = True

    if changed:
        memory["recent_queries"] = recent_queries
        memory["recent_product_slugs"] = recent_product_slugs
        memory["updated_at"] = utc_now().isoformat()
        profile["memory"] = memory
        return profile, True
    return original, False


def _cross_sell_available(user: User) -> bool:
    if not settings.CROSS_SELL_ENABLED:
        return False
    profile = user.profile_json if isinstance(user.profile_json, dict) else {}
    last_ts = profile.get("cross_sell_ts") if isinstance(profile, dict) else None
    last_time = parse_timestamp(last_ts) if isinstance(last_ts, str) else None
    if last_time:
        delta_min = (utc_now() - last_time).total_seconds() / 60
        if delta_min < settings.CROSS_SELL_COOLDOWN_MIN:
            return False
    return True


async def _maybe_add_cross_sell(
    session: AsyncSession,
    user: User,
    matched_products: list[Product],
    allow: bool,
) -> list[Product]:
    if not allow or not _cross_sell_available(user):
        return matched_products
    cross_sell = await find_cross_sell_product(session, matched_products)
    if not cross_sell:
        return matched_products
    if cross_sell.id in {product.id for product in matched_products}:
        return matched_products
    profile = user.profile_json if isinstance(user.profile_json, dict) else {}
    if isinstance(profile, dict):
        profile["cross_sell_ts"] = utc_now().isoformat()
        user.profile_json = profile
        await session.commit()
    await log_event(
        session,
        level="info",
        event_type="cross_sell_suggested",
        data={
            "user_id": user.id,
            "product_id": cross_sell.id,
            "product_slug": cross_sell.slug,
        },
    )
    return matched_products + [cross_sell]


def _should_schedule_followup(
    behavior_match: BehaviorMatch | None,
    order_intent: bool,
    product_intent: bool,
    matched_products: list[Product] | None,
) -> bool:
    if not matched_products:
        return False
    if order_intent:
        return True
    if behavior_match and behavior_match.pattern in FOLLOWUP_PATTERNS:
        return True
    return bool(product_intent)


def _merge_pref_values(
    base: dict[str, Any] | None, updates: dict[str, Any] | None
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base or {})
    for key, value in (updates or {}).items():
        if value is None:
            continue
        if isinstance(value, list):
            existing = merged.get(key)
            if isinstance(existing, list):
                merged[key] = list(dict.fromkeys(existing + value))
            else:
                merged[key] = list(dict.fromkeys(value))
        else:
            merged[key] = value
    return merged


def _merge_recent_user_text(
    history: list[Message], window_sec: float
) -> str | None:
    if window_sec <= 0 or not history:
        return None
    recent: list[str] = []
    latest_time: datetime | None = None
    for msg in reversed(history):
        if msg.role != "user" or msg.type == "read":
            break
        if not msg.content_text:
            continue
        if latest_time is None:
            latest_time = msg.created_at
        if msg.created_at and latest_time:
            if (latest_time - msg.created_at).total_seconds() > window_sec:
                break
        recent.append(msg.content_text.strip())
    if len(recent) <= 1:
        return None
    return "\n".join(reversed(recent))


def _required_fields_for_tags(query_tags: Any) -> list[str]:
    categories = set(query_tags.categories)
    if not categories:
        return DEFAULT_REQUIRED_FIELDS
    if categories & SHOE_CATEGORIES:
        return DEFAULT_REQUIRED_FIELDS
    if categories & APPAREL_CATEGORIES:
        return ["gender", "size", "budget"]
    if categories & COSMETIC_CATEGORIES:
        return ["color", "budget"]
    if categories & PERFUME_CATEGORIES:
        return ["gender", "budget"]
    if categories & ACCESSORY_CATEGORIES:
        return ["gender", "budget"]
    return ["budget"]


def _build_filled_slots(
    query_tags: Any, prefs: dict[str, Any] | None, updates: dict[str, Any]
) -> dict[str, Any]:
    merged = _merge_pref_values(prefs, updates)
    slots: dict[str, Any] = {}
    if query_tags.categories:
        slots["category"] = list(query_tags.categories)
    elif merged.get("categories"):
        slots["category"] = merged.get("categories")
    if query_tags.genders:
        slots["gender"] = list(query_tags.genders)
    elif merged.get("gender"):
        slots["gender"] = merged.get("gender")
    if query_tags.sizes:
        slots["size"] = list(query_tags.sizes)
    elif merged.get("sizes"):
        slots["size"] = merged.get("sizes")
    if query_tags.styles:
        slots["style"] = list(query_tags.styles)
    elif merged.get("styles"):
        slots["style"] = merged.get("styles")
    if query_tags.colors:
        slots["color"] = list(query_tags.colors)
    elif merged.get("colors"):
        slots["color"] = merged.get("colors")
    budget_min = merged.get("budget_min")
    budget_max = merged.get("budget_max")
    if isinstance(budget_min, int) or isinstance(budget_max, int):
        slots["budget"] = {"min": budget_min, "max": budget_max}
    return slots


def _find_last_store_topic(logs: list[AppLog]) -> str | None:
    for log in reversed(logs):
        data = log.data or {}
        if data.get("intent") == "store_info":
            topic = data.get("store_topic")
            if isinstance(topic, str) and topic:
                return topic
    return None


def _coerce_product_id(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


async def _resolve_recent_product_choice(
    session: AsyncSession,
    conversation_id: int,
    limit: int = 5,
) -> tuple[Product | None, int]:
    logs = await get_recent_response_logs(session, conversation_id, limit)
    for log in reversed(logs):
        data = log.data or {}
        product_ids = data.get("product_ids")
        if isinstance(product_ids, list) and product_ids:
            ids = [value for value in (_coerce_product_id(item) for item in product_ids) if value]
            if ids:
                if len(ids) == 1:
                    product = await session.get(Product, ids[0])
                    return product, len(ids)
                return None, len(ids)
        product_slugs = data.get("product_slugs")
        if isinstance(product_slugs, list) and product_slugs:
            slugs = [slug for slug in product_slugs if isinstance(slug, str) and slug.strip()]
            if slugs:
                if len(slugs) == 1:
                    result = await session.execute(
                        select(Product).where(Product.slug == slugs[0])
                    )
                    product = result.scalars().first()
                    return product, len(slugs)
                return None, len(slugs)
    return None, 0


def _build_store_plan_for_topic(topic: str | None) -> OutboundPlan | None:
    if topic == "contact":
        return build_contact_plan()
    if topic == "address":
        return build_branches_plan()
    if topic == "hours":
        return OutboundPlan(type="text", text=build_hours_response())
    if topic == "phone":
        return OutboundPlan(type="text", text=build_phone_response())
    if topic == "website":
        return build_website_plan()
    if topic == "trust":
        return OutboundPlan(type="text", text=build_trust_response())
    return None


def resolve_repeat_plan(
    *,
    store_topic: str | None,
    last_bot_action: str | None,
    last_bot_answers: dict[str, object] | None,
    last_assistant_text: str | None,
) -> tuple[OutboundPlan | None, dict[str, object]]:
    meta: dict[str, object] = {}
    plan = _build_store_plan_for_topic(store_topic)
    if plan:
        if store_topic:
            meta["store_topic"] = store_topic
        meta["repeat_source"] = "store_plan"
        return plan, meta

    answers = last_bot_answers if isinstance(last_bot_answers, dict) else {}
    if store_topic:
        key = f"store_info:{store_topic}"
        cached = answers.get(key)
        if isinstance(cached, str) and cached.strip():
            meta["store_topic"] = store_topic
            meta["repeat_source"] = "cached_store"
            return OutboundPlan(type="text", text=cached), meta

    if last_bot_action:
        cached = answers.get(last_bot_action)
        if isinstance(cached, str) and cached.strip():
            meta["repeat_source"] = "cached_intent"
            return OutboundPlan(type="text", text=cached), meta

    if last_assistant_text:
        meta["repeat_source"] = "history"
        return OutboundPlan(type="text", text=last_assistant_text), meta

    return None, meta


async def _update_product_state(
    session: AsyncSession,
    user: User,
    query: str,
    offset: int,
    total: int,
) -> None:
    profile = user.profile_json if isinstance(user.profile_json, dict) else {}
    if not query:
        profile.pop("product_state", None)
    else:
        profile["product_state"] = {
            "query": query,
            "offset": offset,
            "total": total,
            "updated_at": utc_now().isoformat(),
        }
    user.profile_json = profile
    await session.commit()


def _build_match_debug(matches: list[Any]) -> list[dict[str, Any]]:
    debug: list[dict[str, Any]] = []
    for match in matches[: settings.PRODUCT_MATCH_LIMIT]:
        product = match.product
        debug.append(
            {
                "id": product.id,
                "slug": product.slug,
                "score": match.score,
                "matched_tokens": list(match.matched_tokens),
                "matched_tags": list(match.matched_tags),
                "matched_brands": list(getattr(match, "matched_brands", ())),
            }
        )
    return debug


def _split_show_products(text: str) -> tuple[bool, str]:
    if not text:
        return False, text
    if SHOW_PRODUCTS_TOKEN in text or SHOW_PRODUCTS_TOKEN_ALT in text:
        cleaned = text.replace(SHOW_PRODUCTS_TOKEN, "").replace(SHOW_PRODUCTS_TOKEN_ALT, "")
        cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()
        return True, cleaned
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines).strip()
    return False, cleaned


def _missing_required_fields(
    query_tags: Any,
    fresh_prefs: dict[str, Any] | None,
    required_fields: list[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    missing: list[str] = []
    known: dict[str, str] = {}
    prefs = fresh_prefs or {}
    required_fields = required_fields or DEFAULT_REQUIRED_FIELDS

    if "category" in required_fields:
        if query_tags.categories:
            known["category"] = "، ".join(query_tags.categories)
        else:
            missing.append("category")

    if "gender" in required_fields:
        gender = None
        if query_tags.genders:
            gender = "، ".join(query_tags.genders)
        elif isinstance(prefs.get("gender"), str):
            gender = prefs["gender"]
        if gender:
            known["gender"] = gender
        else:
            missing.append("gender")

    if "size" in required_fields:
        size = None
        if query_tags.sizes:
            size = "، ".join(query_tags.sizes)
        else:
            pref_sizes = prefs.get("sizes")
            if isinstance(pref_sizes, list) and pref_sizes:
                size = "، ".join(str(item) for item in pref_sizes)
        if size:
            known["size"] = size
        else:
            missing.append("size")

    if "style" in required_fields:
        style = None
        if query_tags.styles:
            style = "، ".join(query_tags.styles)
        if style:
            known["style"] = style
        else:
            missing.append("style")

    if "color" in required_fields:
        color = None
        if query_tags.colors:
            color = "، ".join(query_tags.colors)
        else:
            pref_colors = prefs.get("colors")
            if isinstance(pref_colors, list) and pref_colors:
                color = "، ".join(str(item) for item in pref_colors)
        if color:
            known["color"] = color
        else:
            missing.append("color")

    if "budget" in required_fields:
        budget_min = prefs.get("budget_min") if isinstance(prefs.get("budget_min"), int) else None
        budget_max = prefs.get("budget_max") if isinstance(prefs.get("budget_max"), int) else None
        if budget_min is not None or budget_max is not None:
            if budget_min is not None and budget_max is not None:
                known["budget"] = f"{budget_min:,} تا {budget_max:,} تومان"
            elif budget_min is not None:
                known["budget"] = f"از {budget_min:,} تومان به بالا"
            else:
                known["budget"] = f"تا {budget_max:,} تومان"
        else:
            missing.append("budget")

    return missing, known


def _format_required_question(missing: list[str], known: dict[str, str]) -> str:
    known_parts = []
    for key, label in (("gender", "جنسیت"), ("size", "سایز"), ("style", "سبک"), ("budget", "بازه قیمت")):
        if key in known:
            known_parts.append(f"{label}: {known[key]}")
    prefix = ""
    if known_parts:
        prefix = f"{' | '.join(known_parts)}. "
    if not missing:
        return prefix + "برای معرفی دقیق‌تر، لطفاً اسم دقیق مدل یا عکسش رو بفرستید."
    labels = [REQUIRED_FIELD_LABELS[field] for field in missing]
    if len(labels) == 1:
        ask = labels[0]
    elif len(labels) == 2:
        ask = " و ".join(labels)
    else:
        ask = "، ".join(labels[:-1]) + " و " + labels[-1]
    return prefix + f"برای معرفی دقیق‌تر، لطفاً {ask} رو بگید."


def _format_required_question_alt(missing: list[str], known: dict[str, str]) -> str:
    known_parts = []
    for key, label in (("gender", "جنسیت"), ("size", "سایز"), ("style", "سبک"), ("budget", "بازه قیمت")):
        if key in known:
            known_parts.append(f"{label}: {known[key]}")
    prefix = ""
    if known_parts:
        prefix = f"{' | '.join(known_parts)}. "
    labels = [REQUIRED_FIELD_LABELS[field] for field in missing] if missing else []
    if not labels:
        return prefix + "برای معرفی دقیق‌تر، لطفاً اسم دقیق مدل یا عکسش رو بفرستید."
    if len(labels) == 1:
        ask = labels[0]
    elif len(labels) == 2:
        ask = " و ".join(labels)
    else:
        ask = "، ".join(labels[:-1]) + " و " + labels[-1]
    return prefix + f"برای اینکه دقیق پیشنهاد بدم، فقط {ask} رو بفرستید."


def _last_assistant_text(history: list[Message]) -> str | None:
    recent = _recent_assistant_texts(history, limit=1)
    return recent[0] if recent else None


def _recent_assistant_texts(history: list[Message], limit: int = 3) -> list[str]:
    if limit <= 0:
        return []
    texts: list[str] = []
    for item in reversed(history):
        if item.role != "assistant" or not item.content_text:
            continue
        cleaned = item.content_text.strip()
        if not cleaned:
            continue
        texts.append(cleaned)
        if len(texts) >= limit:
            break
    return texts


def _contains_required_fields(text: str, missing: list[str]) -> bool:
    if not text:
        return False
    if not missing:
        lowered = text.lower()
        return any(keyword in lowered for keyword in ["مدل", "عکس", "تصویر"])
    lowered = text.lower()
    checks = {
        "gender": ["جنسیت", "آقا", "خانم", "مردانه", "زنانه", "بچگانه"],
        "size": ["سایز", "اندازه"],
        "style": ["رسمی", "اسپرت", "روزمره", "کلاسیک"],
        "budget": ["قیمت", "تومان", "بازه", "بودجه"],
        "color": ["رنگ", "رنگی", "مشکی", "سفید"],
        "category": ["دسته", "مدل", "نوع", "کفش", "لباس", "عطر", "آرایشی"],
    }
    return all(any(keyword in lowered for keyword in checks[field]) for field in missing)


def _is_low_signal(text: str | None) -> bool:
    if not text:
        return False
    tokens = [token for token in text.strip().split() if token]
    return len(tokens) <= 1


def _rank_products_by_prefs(
    products: list[Product],
    prefs: dict[str, Any] | None,
) -> list[Product]:
    if not products or not prefs:
        return products
    tokens: list[str] = []
    for key in ("categories", "gender", "colors"):
        value = prefs.get(key)
        if isinstance(value, list):
            tokens.extend([item for item in value if isinstance(item, str)])
        elif isinstance(value, str):
            tokens.append(value)
    tokens = [token.strip().lower() for token in tokens if token and token.strip()]
    budget_min = prefs.get("budget_min") if isinstance(prefs.get("budget_min"), int) else None
    budget_max = prefs.get("budget_max") if isinstance(prefs.get("budget_max"), int) else None
    if not tokens and budget_min is None and budget_max is None:
        return products
    if budget_min is not None or budget_max is not None:
        in_budget = []
        for product in products:
            if product.price is None:
                continue
            if (budget_min is None or product.price >= budget_min) and (
                budget_max is None or product.price <= budget_max
            ):
                in_budget.append(product)
        if in_budget:
            products = in_budget
    scored: list[tuple[int, datetime, Product]] = []
    for product in products:
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
        score = sum(1 for token in tokens if token in haystack)
        if product.price is not None and (budget_min is not None or budget_max is not None):
            if (budget_min is None or product.price >= budget_min) and (
                budget_max is None or product.price <= budget_max
            ):
                score += 1
        scored.append((score, product.updated_at or datetime.min, product))
    max_score = max(item[0] for item in scored) if scored else 0
    if max_score <= 0:
        return products
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored]

SALES_KEYWORDS = {
    "price",
    "pricing",
    "buy",
    "order",
    "purchase",
    "قیمت",
    "خرید",
    "سفارش",
    "پرداخت",
}
SUPPORT_KEYWORDS = {
    "problem",
    "issue",
    "error",
    "refund",
    "complaint",
    "support",
    "مشکل",
    "خرابی",
    "خطا",
    "شکایت",
    "مرجوع",
    "پشتیبانی",
}
FAQ_MATCH_MIN_LEN = 4


def normalize_webhook(payload: dict[str, Any]) -> NormalizedMessage:
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)

    sender_id = payload.get("sender")
    receiver_id = payload.get("receiver")
    message_type = payload.get("message_type")
    if not sender_id or not receiver_id or not message_type:
        raise ValueError("Missing sender, receiver, or message_type")

    raw_type = str(message_type).lower().strip()
    if raw_type in {"image", "photo", "picture", "video", "media"}:
        message_type = "media"
    elif raw_type in {"audio", "voice"}:
        message_type = "audio"
    elif raw_type in {"text", "quick_reply", "postback", "button", "interactive"}:
        message_type = "text"
    elif raw_type == "read":
        message_type = "read"
    else:
        raise ValueError("Unsupported message_type")

    text = payload.get("text")
    if not text:
        payload_value = payload.get("payload")
        if isinstance(payload_value, str):
            text = payload_value
        else:
            quick_reply = payload.get("quick_reply")
            if isinstance(quick_reply, dict):
                text = quick_reply.get("payload") or quick_reply.get("title")
            postback = payload.get("postback")
            if not text and isinstance(postback, dict):
                text = postback.get("payload") or postback.get("title")
            message_value = payload.get("message")
            if not text and isinstance(message_value, str):
                text = message_value
    timestamp = parse_timestamp(payload.get("timestamp"))

    is_admin = payload.get("is_admin")
    if is_admin is None:
        is_admin = payload.get("admin_is")
    is_admin = _coerce_bool(is_admin) if is_admin is not None else False

    media_url = None
    audio_url = None
    media = payload.get("media")
    if isinstance(media, dict):
        media_url_value = media.get("url")
        media_type = media.get("type")
        media_type = str(media_type).lower().strip() if media_type is not None else None
        if media_url_value is not None:
            if message_type == "audio" or media_type == "audio":
                audio_url = str(media_url_value)
            else:
                media_url = str(media_url_value)

    read_message_id = None
    if message_type == "read":
        read = payload.get("read")
        if isinstance(read, dict):
            read_message_id = read.get("message_id")

    return NormalizedMessage(
        sender_id=str(sender_id),
        receiver_id=str(receiver_id),
        message_type=message_type,
        text=str(text) if text is not None else None,
        media_url=media_url,
        audio_url=audio_url,
        is_admin=is_admin,
        read_message_id=str(read_message_id) if read_message_id is not None else None,
        timestamp=timestamp,
        username=None,
        follow_status=None,
        follower_count=None,
        raw_payload=payload,
    )


def normalize_payload(payload: dict[str, Any]) -> NormalizedMessage:
    return normalize_webhook(payload)


async def enrich_user_profile(message: NormalizedMessage) -> None:
    if (
        message.username
        and message.follow_status
        and message.follower_count is not None
    ):
        return
    if not settings.DIRECTAM_BASE_URL or not settings.SERVICE_API_KEY:
        return

    client = InstagramUserClient()
    try:
        if not message.username:
            message.username = await client.get_username(message.sender_id)
        if not message.follow_status:
            message.follow_status = await client.get_follow_status(message.sender_id)
        if message.follower_count is None:
            message.follower_count = await client.get_follow_count(message.sender_id)
    except InstagramUserClientError as exc:
        logger.warning("user_enrich_failed", error=str(exc))


async def handle_webhook(payload: dict[str, Any]) -> None:
    try:
        normalized = normalize_webhook(payload)
    except ValueError as exc:
        logger.warning("webhook_invalid", error=str(exc))
        return

    if not normalized.is_admin and normalized.message_type != "read":
        await enrich_user_profile(normalized)

    logger.info(
        "webhook_received",
        sender_id=normalized.sender_id,
        message_type=normalized.message_type,
        is_admin=normalized.is_admin,
        has_text=bool(normalized.text),
    )

    async with AsyncSessionLocal() as session:
        try:
            user = await upsert_user(session, normalized)
            conversation = await get_or_create_conversation(session, user.id)
            role = "admin" if normalized.is_admin else "user"

            record = await save_message(session, conversation.id, normalized, role)
            if role == "user" and normalized.message_type != "read":
                conversation.last_user_message_at = normalized.timestamp or utc_now()
            last_user_message_id = record.id if role == "user" else None
            await log_event(
                session,
                level="info",
                event_type="webhook_received",
                data={
                    "sender_id": normalized.sender_id,
                    "message_type": normalized.message_type,
                    "is_admin": normalized.is_admin,
                },
                commit=False,
            )
            await session.commit()

            if normalized.is_admin:
                note_url = normalized.media_url or normalized.audio_url
                if note_url:
                    tag = normalized.text.strip() if normalized.text else None
                    if tag:
                        tag = tag[:64]
                    await create_admin_media_note(
                        session,
                        conversation_id=conversation.id,
                        message_id=record.id,
                        media_url=note_url,
                        tag=tag,
                    )
                    await log_event(
                        session,
                        level="info",
                        event_type="admin_media_ingested",
                        data={
                            "conversation_id": conversation.id,
                            "message_id": record.id,
                            "media_url": note_url,
                        },
                    )
                    await session.commit()
                if normalized.text and normalized.text.strip():
                    stored_policy = await store_admin_policy_memory(
                        session,
                        text=normalized.text,
                        source="admin_webhook",
                        conversation_id=conversation.id,
                        message_id=record.id,
                    )
                    if stored_policy:
                        await session.commit()

            if role == "user" and normalized.message_type != "read":
                await cancel_followups_for_conversation(
                    session, conversation.id, reason="user_activity"
                )

            if (
                role == "user"
                and normalized.message_type != "read"
                and settings.MESSAGE_DEBOUNCE_SEC > 0
            ):
                await asyncio.sleep(settings.MESSAGE_DEBOUNCE_SEC)
                newer = await session.execute(
                    select(Message.id)
                    .where(Message.conversation_id == conversation.id)
                    .where(Message.role == "user")
                    .where(Message.type != "read")
                    .where(Message.id > record.id)
                    .limit(1)
                )
                if newer.scalar_one_or_none():
                    await log_event(
                        session,
                        level="info",
                        event_type="debounce_skip",
                        data={
                            "conversation_id": conversation.id,
                            "message_id": record.id,
                            "sender_id": normalized.sender_id,
                        },
                    )
                    return

            analysis_text = ""
            analysis_terms_text = ""
            analysis_payload: dict[str, Any] | None = None
            if (
                not normalized.is_admin
                and normalized.media_url
                and is_likely_image_url(normalized.media_url)
            ):
                analysis = await analyze_image_url(
                    normalized.media_url,
                    normalized.text,
                )
                if analysis:
                    analysis_text = (
                        analysis.get("analysis_text")
                        or analysis.get("summary")
                        or ""
                    )
                    terms = analysis.get("search_terms")
                    if isinstance(terms, list):
                        clean_terms = [
                            str(term).strip()
                            for term in terms
                            if isinstance(term, str) and str(term).strip()
                        ]
                        if clean_terms:
                            analysis_terms_text = " ".join(clean_terms[:8])
                    analysis_payload = analysis
                    payload = record.payload_json or {}
                    payload["media_analysis"] = analysis
                    record.payload_json = payload
                    await session.commit()

            if normalized.is_admin:
                logger.info("admin_ignored", sender_id=normalized.sender_id)
                return
            if normalized.message_type == "read":
                logger.info("read_ignored", sender_id=normalized.sender_id)
                return

            bot_settings = await get_active_bot_settings(session)
            max_history = (
                bot_settings.max_history_messages
                if bot_settings and bot_settings.max_history_messages
                else settings.MAX_HISTORY_MESSAGES
            )
            history_limit = max_history
            if settings.LLM_MAX_USER_TURNS > 0:
                history_limit = min(
                    history_limit, settings.LLM_MAX_USER_TURNS * 2 + 6
                )
            history_limit = max(history_limit, 1)
            history = await get_recent_history(
                session, conversation.id, history_limit
            )
            merged_text = _merge_recent_user_text(
                history, settings.MESSAGE_DEBOUNCE_SEC
            )
            if merged_text and merged_text != (normalized.text or "").strip():
                normalized.text = merged_text
                await log_event(
                    session,
                    level="info",
                    event_type="debounce_merge",
                    data={
                        "conversation_id": conversation.id,
                        "message_id": record.id,
                        "sender_id": normalized.sender_id,
                    },
                    commit=False,
                )
                await session.commit()
            recent_assistant_texts = _recent_assistant_texts(history, limit=3)
            last_assistant_text = recent_assistant_texts[0] if recent_assistant_texts else None
            is_first_message = (
                sum(1 for msg in history if msg.role == "user" and msg.type != "read")
                <= 1
            )
            catalog_snapshot = await get_catalog_snapshot(session)
            catalog_summary = catalog_snapshot.summary if catalog_snapshot else None
            behavior_match: BehaviorMatch | None = None
            behavior_summary: dict[str, int] = {}
            behavior_recent: list[dict[str, Any]] = []
            behavior_meta: dict[str, Any] | None = None
            behavior_snapshot: dict[str, Any] | None = None
            def _merge_meta(extra: dict[str, Any] | None) -> dict[str, Any] | None:
                if behavior_meta is None and not extra:
                    return None
                merged: dict[str, Any] = {}
                if behavior_meta:
                    merged.update(behavior_meta)
                if extra:
                    merged.update(extra)
                return merged

            llm_first_all = settings.LLM_FIRST_ALL
            intent_text = (merged_text or normalized.text or "").strip()
            query_text = " ".join(
                part for part in [intent_text, analysis_text, analysis_terms_text] if part
            ).strip()
            lowered = intent_text.lower()
            behavior_input = intent_text or analysis_text
            conversation_state_payload: dict[str, Any] | None = None
            router_decision = route_intent(query_text or intent_text)
            router_intent = router_decision.intent
            router_category = router_decision.category
            router_confidence = router_decision.confidence
            router_evidence = list(router_decision.evidence_keywords)
            router_risk = router_decision.risk_level

            async def _touch_state(
                intent: str,
                category: str | None = None,
                required_slots: list[str] | None = None,
                filled_slots: dict[str, Any] | None = None,
                selected_product: dict[str, Any] | None = None,
                preserve_selected_product: bool = True,
                last_handler_used: str | None = None,
                increment_loop: bool = False,
                reset_loop: bool = False,
            ) -> dict[str, Any] | None:
                state = await get_or_create_state(session, conversation.id)
                prior_payload = build_state_payload(state)
                state = await update_state(
                    session,
                    conversation.id,
                    intent,
                    category or infer_state_category(query_text),
                    required_slots,
                    filled_slots,
                    intent_text,
                    state=state,
                    selected_product=selected_product,
                    preserve_selected_product=preserve_selected_product,
                    last_user_message_id=last_user_message_id,
                    last_handler_used=last_handler_used,
                    increment_loop=increment_loop,
                    reset_loop=reset_loop,
                )
                next_payload = build_state_payload(state)
                await log_event(
                    session,
                    level="info",
                    event_type="state_updated",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "prior_state": prior_payload,
                        "next_state": next_payload,
                    },
                    commit=False,
                )
                await session.commit()
                return next_payload
            if behavior_input:
                behavior_match, behavior_summary, behavior_recent = await analyze_user_behavior(
                    session,
                    user.id,
                    behavior_input,
                    settings.BEHAVIOR_HISTORY_LIMIT,
                )
                behavior_profile = await upsert_behavior_profile(
                    session,
                    user_id=user.id,
                    conversation_id=conversation.id,
                    match=behavior_match,
                    last_message=behavior_input,
                    summary_counts=behavior_summary,
                    recent_payload=behavior_recent,
                )
                behavior_snapshot = build_behavior_snapshot(
                    behavior_profile,
                    behavior_input,
                    behavior_summary,
                    behavior_recent,
                )
                if behavior_match:
                    behavior_meta = {
                        "behavior_pattern": behavior_match.pattern,
                        "behavior_confidence": behavior_match.confidence,
                    }
                    await log_event(
                        session,
                        level="info",
                        event_type="pattern_detected",
                        data={
                            "user_id": user.id,
                            "conversation_id": conversation.id,
                            "pattern": behavior_match.pattern,
                            "confidence": behavior_match.confidence,
                            "reason": behavior_match.reason,
                            "keywords": list(behavior_match.keywords),
                            "tags": list(behavior_match.tags),
                        },
                        commit=False,
                    )
                    await session.commit()

                store_intent = router_intent == "store_info"
                if not llm_first_all:
                    if is_thanks(lowered):
                        conversation_state_payload = await _touch_state(
                            "unknown",
                            category=infer_state_category(query_text),
                        )
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            build_thanks_response(),
                            meta=_merge_meta({"source": "guardrails", "intent": "thanks"}),
                        )
                        return
                    if is_decline(lowered):
                        conversation_state_payload = await _touch_state(
                            "unknown",
                            category=infer_state_category(query_text),
                        )
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            build_decline_response(),
                            meta=_merge_meta({"source": "guardrails", "intent": "decline"}),
                        )
                        return
                    if is_goodbye(lowered):
                        conversation_state_payload = await _touch_state(
                            "unknown",
                            category=infer_state_category(query_text),
                        )
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            build_goodbye_response(),
                            meta=_merge_meta({"source": "guardrails", "intent": "goodbye"}),
                        )
                        return
                    if store_intent:
                        store_topic = None
                        if wants_hours(lowered):
                            store_topic = "hours"
                        elif wants_address(lowered):
                            store_topic = "address"
                        elif wants_phone(lowered):
                            store_topic = "phone"
                        elif wants_website(lowered):
                            store_topic = "website"
                        elif wants_trust(lowered):
                            store_topic = "trust"
                        rule_plan = build_rule_based_plan(
                            normalized.message_type,
                            normalized.text,
                            is_first_message,
                        )
                        if rule_plan:
                            conversation_state_payload = await _touch_state(
                                "store_info",
                                category=infer_state_category(query_text),
                                last_handler_used="store_info",
                                reset_loop=True,
                            )
                            await send_plan_and_store(
                                session,
                                conversation.id,
                                normalized.sender_id,
                                rule_plan,
                                meta=_merge_meta({
                                    "source": "guardrails",
                                    "intent": "store_info",
                                    "handler": "store_info",
                                    "store_topic": store_topic,
                                }),
                            )
                            return

            if behavior_snapshot is None:
                profile = await get_behavior_profile(session, user.id)
                behavior_snapshot = build_behavior_snapshot(
                    profile, behavior_input, behavior_summary, behavior_recent
                )

            support_intent = router_intent == "complaint_support"
            if behavior_match and behavior_match.pattern in {"angry_customer", "checkout_help"}:
                support_intent = True
            if any(keyword in lowered for keyword in SUPPORT_KEYWORDS):
                support_intent = True

            state = await get_or_create_state(session, conversation.id)
            selected_product_state = (
                state.selected_product if isinstance(state.selected_product, dict) else None
            )
            url_slug = _extract_product_slug(intent_text)
            product_from_url: Product | None = None
            if url_slug:
                result = await session.execute(
                    select(Product).where(
                        (Product.slug == url_slug)
                        | Product.page_url.ilike(f"%/product/{url_slug}%")
                    )
                )
                product_from_url = result.scalars().first()
                if product_from_url:
                    selected_product_state = build_selected_product_payload(product_from_url)

            if wants_repeat(intent_text):
                conversation_state_payload = await _touch_state(
                    state.intent or "unknown",
                    category=state.category or infer_state_category(query_text),
                    required_slots=state.slots_required,
                    filled_slots=state.slots_filled,
                    last_handler_used="repeat",
                    reset_loop=True,
                )
                explicit_topic = None
                if wants_contact(lowered):
                    explicit_topic = "contact"
                elif wants_hours(lowered):
                    explicit_topic = "hours"
                elif wants_address(lowered):
                    explicit_topic = "address"
                elif wants_phone(lowered):
                    explicit_topic = "phone"
                elif wants_website(lowered):
                    explicit_topic = "website"
                elif wants_trust(lowered):
                    explicit_topic = "trust"

                store_topic = explicit_topic
                if store_topic is None:
                    recent_logs = await get_recent_response_logs(
                        session, conversation.id, max(5, settings.RESPONSE_LOG_CONTEXT_LIMIT)
                    )
                    store_topic = _find_last_store_topic(recent_logs)
                plan, repeat_meta = resolve_repeat_plan(
                    store_topic=store_topic,
                    last_bot_action=state.last_bot_action,
                    last_bot_answers=state.last_bot_answer_by_intent
                    if isinstance(state.last_bot_answer_by_intent, dict)
                    else {},
                    last_assistant_text=last_assistant_text,
                )
                if plan:
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        plan,
                        meta=_merge_meta({
                            "source": "guardrails",
                            "intent": "repeat",
                            "handler": "repeat",
                            **repeat_meta,
                        }),
                    )
                    await log_event(
                        session,
                        level="info",
                        event_type="repeat_handled",
                        data={
                            "conversation_id": conversation.id,
                            "user_id": user.id,
                            "store_topic": store_topic,
                        },
                    )
                    return

            if is_negative_feedback(lowered):
                loop_payload = await _touch_state(
                    state.intent or "unknown",
                    category=state.category or infer_state_category(query_text),
                    required_slots=state.slots_required,
                    filled_slots=state.slots_filled,
                    selected_product=selected_product_state,
                    preserve_selected_product=True,
                    last_handler_used="loop_breaker",
                    increment_loop=True,
                )
                loop_count = 0
                if isinstance(loop_payload, dict):
                    loop_count = int(loop_payload.get("loop_counter") or 0)
                await log_event(
                    session,
                    level="info",
                    event_type="loop_detected",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "reason": "negative_feedback",
                        "loop_counter": loop_count,
                    },
                    commit=False,
                )
                await session.commit()
                escalated_ticket = None
                if settings.LOOP_AUTO_ESCALATE_ENABLED:
                    escalated_ticket = await auto_escalate_loop_to_operator(
                        session,
                        user_id=user.id,
                        conversation_id=conversation.id,
                        loop_counter=loop_count,
                        threshold=settings.LOOP_ESCALATION_THRESHOLD,
                        cooldown_minutes=settings.LOOP_ESCALATION_COOLDOWN_MIN,
                        reason="negative_feedback",
                        last_message=intent_text or behavior_input,
                    )
                if escalated_ticket:
                    reply_text = (
                        "برای جلوگیری از تکرار، گفتگو به اپراتور ارجاع شد. "
                        "همکار پشتیبانی خیلی زود ادامه می‌دهد."
                    )
                elif router_intent == "store_info":
                    reply_text = (
                        "حق با شماست، اشتباه شد. "
                        "منظورتون لینک دسته‌بندی محصولات تو سایت هست یا آدرس شعبه‌ها؟"
                    )
                elif support_intent:
                    reply_text = build_angry_response()
                else:
                    reply_text = (
                        "حق با شماست، اشتباه شد 😔 "
                        "اسم دقیق مدل یا یه عکس از محصول رو بفرستید تا لینک درستش رو بدم."
                    )
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    OutboundPlan(type="text", text=reply_text),
                    meta=_merge_meta({
                        "source": "guardrails",
                        "intent": "loop_breaker",
                        "handler": "loop_breaker",
                        "loop_counter": loop_count,
                        "ticket_id": escalated_ticket.id if escalated_ticket else None,
                        "auto_escalated": bool(escalated_ticket),
                    }),
                )
                return

            token_count = len(lowered.split()) if lowered else 0
            if is_greeting(lowered) and token_count <= 3 and router_intent in {"smalltalk", "unknown"}:
                conversation_state_payload = await _touch_state(
                    "unknown",
                    category=state.category or infer_state_category(query_text),
                    last_handler_used="greeting",
                    reset_loop=True,
                )
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    OutboundPlan(type="text", text=_build_personalized_greeting(user)),
                    meta=_merge_meta({
                        "source": "guardrails",
                        "intent": "greeting",
                        "handler": "greeting",
                    }),
                )
                return

            link_request = wants_product_link(intent_text)
            purchase_confirm = is_purchase_confirmation(intent_text)
            if (link_request or purchase_confirm) and not selected_product_state:
                recent_product, recent_count = await _resolve_recent_product_choice(
                    session, conversation.id
                )
                if recent_product:
                    selected_product_state = build_selected_product_payload(recent_product)
                elif recent_count > 1:
                    conversation_state_payload = await _touch_state(
                        "product_search",
                        category=infer_state_category(query_text),
                        required_slots=state.slots_required,
                        filled_slots=state.slots_filled,
                    )
                    clarification = (
                        "کدوم مدل مدنظرتونه؟ لطفاً اسم دقیق یا لینک محصول رو بفرستید."
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        clarification,
                        meta=_merge_meta({
                            "source": "guardrails",
                            "intent": "product_disambiguate",
                        }),
                    )
                    return

            if link_request:
                page_url = None
                if isinstance(selected_product_state, dict):
                    page_url = selected_product_state.get("page_url")
                if page_url:
                    conversation_state_payload = await _touch_state(
                        "product_selected",
                        category=infer_state_category(query_text),
                        selected_product=selected_product_state,
                        preserve_selected_product=False,
                        last_handler_used="product_link",
                        reset_loop=True,
                    )
                    reply_text = f"حتماً 🙂 لینک مستقیم محصول: {page_url}"
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        OutboundPlan(type="text", text=reply_text),
                        meta=_merge_meta({
                            "source": "guardrails",
                            "intent": "product_link",
                            "handler": "product_link",
                            "product_id": selected_product_state.get("product_id")
                            if isinstance(selected_product_state, dict)
                            else None,
                        }),
                    )
                    await log_event(
                        session,
                        level="info",
                        event_type="link_request_handled",
                        data={
                            "conversation_id": conversation.id,
                            "user_id": user.id,
                            "page_url": page_url,
                        },
                    )
                    return
                conversation_state_payload = await _touch_state(
                    "product_search",
                    category=infer_state_category(query_text),
                    last_handler_used="product_link_missing",
                    reset_loop=True,
                )
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    OutboundPlan(
                        type="text",
                        text="برای ارسال لینک، لطفاً اسم دقیق مدل یا یک عکس/لینک از محصول بفرستید.",
                    ),
                    meta=_merge_meta({
                        "source": "guardrails",
                        "intent": "product_link_missing",
                        "handler": "product_link_missing",
                    }),
                )
                await log_event(
                    session,
                    level="info",
                    event_type="link_request_handled",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "page_url": None,
                    },
                )
                return

            if purchase_confirm and selected_product_state:
                conversation_state_payload = await _touch_state(
                    "order_flow",
                    category=infer_state_category(query_text),
                    selected_product=selected_product_state,
                    preserve_selected_product=False,
                    last_handler_used="order_flow",
                    reset_loop=True,
                )
                reply_text = "حتماً 🙂 برای ثبت سفارش، لطفاً سایز/رنگ و تعداد مدنظرتون رو بگید."
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    OutboundPlan(type="text", text=reply_text),
                    meta=_merge_meta({
                        "source": "order_flow",
                        "intent": "order_flow",
                        "handler": "order_flow",
                        "product_id": selected_product_state.get("product_id")
                        if isinstance(selected_product_state, dict)
                        else None,
                    }),
                )
                await log_event(
                    session,
                    level="info",
                    event_type="selected_product_locked",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "selected_product": selected_product_state,
                    },
                )
                return

            store_info_intent = router_intent == "store_info"
            if not store_info_intent:
                store_info_intent = (
                    wants_contact(lowered)
                    or wants_website(lowered)
                    or wants_address(lowered)
                    or wants_hours(lowered)
                    or wants_phone(lowered)
                    or wants_trust(lowered)
                )
            if store_info_intent:
                store_topic = None
                if wants_contact(lowered):
                    store_topic = "contact"
                elif wants_hours(lowered):
                    store_topic = "hours"
                elif wants_address(lowered):
                    store_topic = "address"
                elif wants_phone(lowered):
                    store_topic = "phone"
                elif wants_website(lowered):
                    store_topic = "website"
                elif wants_trust(lowered):
                    store_topic = "trust"
                rule_plan = build_rule_based_plan(
                    normalized.message_type,
                    intent_text,
                    is_first_message,
                )
                if rule_plan:
                    conversation_state_payload = await _touch_state(
                        "store_info",
                        category=infer_state_category(query_text),
                        last_handler_used="store_info",
                        reset_loop=True,
                    )
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        rule_plan,
                        meta=_merge_meta({
                            "source": "guardrails",
                            "intent": "store_info",
                            "handler": "store_info",
                            "store_topic": store_topic,
                        }),
                    )
                    return

            if llm_first_all:
                token_count = len(intent_text.split()) if intent_text else 0
                if is_thanks(lowered) and token_count <= 4:
                    conversation_state_payload = await _touch_state(
                        "unknown",
                        category=infer_state_category(query_text),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        build_thanks_response(),
                        meta=_merge_meta({"source": "guardrails", "intent": "thanks"}),
                    )
                    return
                if is_decline(lowered) and token_count <= 6:
                    conversation_state_payload = await _touch_state(
                        "unknown",
                        category=infer_state_category(query_text),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        build_decline_response(),
                        meta=_merge_meta({"source": "guardrails", "intent": "decline"}),
                    )
                    return
                if is_goodbye(lowered) and token_count <= 4:
                    conversation_state_payload = await _touch_state(
                        "unknown",
                        category=infer_state_category(query_text),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        build_goodbye_response(),
                        meta=_merge_meta({"source": "guardrails", "intent": "goodbye"}),
                    )
                    return
                if is_greeting(lowered) and token_count <= 2:
                    conversation_state_payload = await _touch_state(
                        "unknown",
                        category=infer_state_category(query_text),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        _build_personalized_greeting(user),
                        meta=_merge_meta({"source": "guardrails", "intent": "greeting"}),
                    )
                    return

            continue_request = wants_more_products(intent_text)
            profile = user.profile_json if isinstance(user.profile_json, dict) else {}
            prefs = profile.get("prefs") if isinstance(profile, dict) else None
            if continue_request:
                state = profile.get("product_state") if isinstance(profile, dict) else None
                state_query = state.get("query") if isinstance(state, dict) else None
                state_offset = state.get("offset") if isinstance(state, dict) else None
                state_updated = state.get("updated_at") if isinstance(state, dict) else None
                updated_at = parse_timestamp(state_updated) if isinstance(state_updated, str) else None
                if not state_query or state_offset is None:
                    conversation_state_payload = await _touch_state(
                        "product_search",
                        category=infer_state_category(query_text),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        "برای ادامه لطفاً بگید دنبال چه محصولی بودید.",
                        meta=_merge_meta({"source": "product_match", "intent": "product_more_empty"}),
                    )
                    return
                if updated_at and (utc_now() - updated_at).total_seconds() > settings.PRODUCT_CONTINUE_TTL_SEC:
                    conversation_state_payload = await _touch_state(
                        "product_search",
                        category=infer_state_category(state_query),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        "از آخرین لیست زمان گذشته؛ لطفاً دوباره بگید دنبال چه محصولی هستید.",
                        meta=_merge_meta({"source": "product_match", "intent": "product_more_expired"}),
                    )
                    return
                matches = await match_products_with_scores(
                    session,
                    state_query,
                    limit=max(
                        settings.LLM_PRODUCT_CONTEXT_LIMIT,
                        settings.PRODUCT_MATCH_LIMIT + int(state_offset),
                    ),
                )
                products = [match.product for match in matches]
                products = _rank_products_by_prefs(products, prefs)
                start = int(state_offset)
                end = start + settings.PRODUCT_MATCH_LIMIT
                page = products[start:end]
                if not page:
                    conversation_state_payload = await _touch_state(
                        "product_search",
                        category=infer_state_category(state_query),
                    )
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        "مورد بیشتری پیدا نکردم. اگر مدل خاصی مدنظرتونه بفرستید.",
                        meta=_merge_meta({"source": "product_match", "intent": "product_more_done"}),
                    )
                    return
                product_plan = build_product_plan(state_query, page)
                if product_plan:
                    conversation_state_payload = await _touch_state(
                        "product_search",
                        category=infer_state_category(state_query),
                    )
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        product_plan,
                        meta=_merge_meta({
                            "source": "product_match",
                            "intent": "product_more",
                            "product_ids": [product.id for product in page],
                            "product_slugs": [product.slug for product in page if product.slug],
                        }),
                    )
                await _update_product_state(session, user, state_query, end, len(products))
                if len(products) > end:
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        _build_more_products_plan(),
                        meta=_merge_meta({
                            "source": "product_match",
                            "intent": "product_more_prompt",
                        }),
                    )
                return

            pref_updates: dict[str, Any] = {}
            if query_text:
                pref_updates = extract_preferences(query_text)
                if pref_updates:
                    profile = user.profile_json or {}
                    prefs = profile.get("prefs", {}) if isinstance(profile, dict) else {}
                    changed = False
                    for key, value in pref_updates.items():
                        if value is None:
                            continue
                        if isinstance(value, list):
                            existing = prefs.get(key, [])
                            merged = list(dict.fromkeys((existing or []) + value))
                            if merged != existing:
                                prefs[key] = merged
                                changed = True
                        else:
                            if prefs.get(key) != value:
                                prefs[key] = value
                                changed = True
                    if changed:
                        profile["prefs"] = prefs
                        user.profile_json = profile
                        await session.commit()

            order_intent = bool(behavior_match and behavior_match.pattern == "ready_to_buy")
            if router_intent == "order_intent":
                order_intent = True
            order_plan = await handle_order_flow(session, user, intent_text)
            order_hint_text = None
            if order_plan:
                order_hint_text = _plan_to_text(order_plan)
                order_intent = True
                conversation_state_payload = await _touch_state(
                    "order_flow",
                    category=infer_state_category(query_text),
                )
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    order_plan,
                    meta=_merge_meta({"source": "order_flow", "intent": "order_flow"}),
                )
                await schedule_followup_task(
                    session,
                    conversation,
                    user,
                    reason="order_flow",
                    payload={"text": order_hint_text},
                )
                return

            if support_intent:
                ticket = await get_or_create_ticket(
                    session,
                    user_id=user.id,
                    conversation_id=conversation.id,
                    summary="درخواست پشتیبانی",
                    last_message=intent_text or behavior_input,
                )
                await log_event(
                    session,
                    level="info",
                    event_type="ticket_created",
                    data={
                        "ticket_id": ticket.id,
                        "user_id": user.id,
                        "conversation_id": conversation.id,
                        "status": ticket.status,
                    },
                    commit=False,
                )
                await session.commit()
                conversation_state_payload = await _touch_state(
                    "support",
                    category=infer_state_category(query_text),
                    last_handler_used="complaint_support",
                    reset_loop=True,
                )
                await send_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    build_angry_response(),
                    meta=_merge_meta({
                        "source": "support_flow",
                        "intent": "complaint_support",
                        "handler": "complaint_support",
                        "ticket_id": ticket.id,
                    }),
                )
                return

            url_slug = _extract_product_slug(intent_text)
            product_from_url: Product | None = None
            if url_slug:
                result = await session.execute(
                    select(Product).where(
                        (Product.slug == url_slug)
                        | Product.page_url.ilike(f"%/product/{url_slug}%")
                    )
                )
                product_from_url = result.scalars().first()

            tokens = tokenize_query(query_text)
            query_tags = infer_tags(query_text)
            wants_products = wants_product_list(query_text)
            needs_details = needs_product_details(query_text)
            visual_product_intent = bool(normalized.media_url and analysis_text)
            store_intent = store_info_intent or is_greeting(lowered)
            product_intent = wants_product_intent(query_text)
            if store_intent or support_intent:
                product_intent = False
            if selected_product_state:
                product_intent = True
                needs_details = False
            elif visual_product_intent:
                product_intent = True
            elif (
                query_tags.categories
                or query_tags.genders
                or query_tags.materials
                or query_tags.styles
            ):
                product_intent = True

            should_match_products = bool(query_text) and (
                product_intent
                or wants_products
                or needs_details
                or visual_product_intent
                or query_tags.categories
                or query_tags.genders
                or query_tags.materials
                or query_tags.styles
                or query_tags.colors
                or query_tags.sizes
            )
            if product_from_url:
                should_match_products = True
            matches_for_context = []
            if should_match_products and not product_from_url:
                matches_for_context = await match_products_with_scores(
                    session,
                    query_text,
                    limit=max(
                        settings.LLM_PRODUCT_CONTEXT_LIMIT,
                        settings.PRODUCT_MATCH_LIMIT,
                    ),
                )
            match_debug = _build_match_debug(matches_for_context)
            matched_products_for_llm = [match.product for match in matches_for_context]
            matched_products = matched_products_for_llm[: settings.PRODUCT_MATCH_LIMIT]
            if product_from_url:
                matched_products_for_llm = [product_from_url]
                matched_products = [product_from_url]
            if should_match_products and not matched_products_for_llm and analysis_text:
                visual_matches = await match_products_with_scores(
                    session,
                    analysis_text,
                    limit=max(
                        settings.LLM_PRODUCT_CONTEXT_LIMIT,
                        settings.PRODUCT_MATCH_LIMIT,
                    ),
                )
                if visual_matches:
                    matches_for_context = visual_matches
                    match_debug = _build_match_debug(matches_for_context)
                    matched_products_for_llm = [match.product for match in matches_for_context]
                    matched_products = matched_products_for_llm[: settings.PRODUCT_MATCH_LIMIT]
            more_results_available = len(matched_products_for_llm) > len(matched_products)

            is_plain_list_request = wants_products and not (
                query_tags.categories
                or query_tags.genders
                or query_tags.materials
                or query_tags.styles
                or query_tags.colors
                or query_tags.sizes
            )
            if wants_products and not matched_products_for_llm and is_plain_list_request:
                result = await session.execute(
                    select(Product)
                    .order_by(Product.updated_at.desc())
                    .limit(settings.LLM_PRODUCT_CONTEXT_LIMIT)
                )
                matched_products_for_llm = list(result.scalars().all())
                matched_products = matched_products_for_llm[: settings.PRODUCT_MATCH_LIMIT]

            prefs = None
            if isinstance(user.profile_json, dict):
                prefs = user.profile_json.get("prefs")
            prefs_current = _merge_pref_values(prefs, pref_updates)
            matched_products_for_llm = _rank_products_by_prefs(
                matched_products_for_llm, prefs_current
            )
            matched_products = _rank_products_by_prefs(matched_products, prefs_current)
            matched_product_ids = [product.id for product in matched_products]
            matched_product_slugs = [product.slug for product in matched_products if product.slug]
            query_tags_meta = {
                "categories": list(query_tags.categories),
                "genders": list(query_tags.genders),
                "styles": list(query_tags.styles),
                "materials": list(query_tags.materials),
                "colors": list(query_tags.colors),
                "sizes": list(query_tags.sizes),
            }
            if should_match_products:
                await log_event(
                    session,
                    level="info",
                    event_type="product_matched",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "query": query_text,
                        "matched_count": len(matched_products_for_llm),
                        "suggest_count": len(matched_products),
                        "product_ids": matched_product_ids,
                        "product_slugs": matched_product_slugs,
                        "query_tags": query_tags_meta,
                        "match_debug": match_debug,
                    },
                    commit=False,
                )
                await session.commit()

            confidence_ok = True
            low_confidence = False
            if product_intent or needs_details or wants_products:
                if product_from_url:
                    confidence_ok = True
                else:
                    top_match = matches_for_context[0] if matches_for_context else None
                    if not top_match:
                        confidence_ok = False
                    else:
                        if tokens:
                            required_score = max(2, len(tokens))
                            if len(tokens) >= 3:
                                required_score = max(3, len(tokens))
                            confidence_ok = top_match.score >= required_score
                        else:
                            confidence_ok = top_match.score >= 2
                if (
                    not tokens
                    and matches_for_context
                    and (
                        query_tags.categories
                        or query_tags.genders
                        or query_tags.materials
                        or query_tags.styles
                        or query_tags.colors
                        or query_tags.sizes
                    )
                ):
                    confidence_ok = True
                low_confidence = not confidence_ok

            if (
                not selected_product_state
                and confidence_ok
                and matched_products
                and router_intent in {"product_specific", "price_availability"}
            ):
                selected_product_state = build_selected_product_payload(matched_products[0])
                await log_event(
                    session,
                    level="info",
                    event_type="selected_product_locked",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "selected_product": selected_product_state,
                        "reason": "router_intent_lock",
                    },
                    commit=False,
                )
                await session.commit()

            required_fields: list[str] = []
            required_known: dict[str, str] = {}
            required_question_text: str | None = None
            if settings.LLM_REQUIRE_FIELDS_ON_LOW_CONF and (
                product_intent or needs_details or wants_products
            ):
                target_fields = _required_fields_for_tags(query_tags)
                required_fields, required_known = _missing_required_fields(
                    query_tags, pref_updates, target_fields
                )
                if required_fields:
                    required_question_text = _format_required_question(
                        required_fields, required_known
                    )
                    required_question_text = _limit_questions(required_question_text, 1)
                    low_confidence = True
            if selected_product_state:
                required_fields = []
                required_known = {}
                required_question_text = None
                low_confidence = False
            low_confidence_block = bool(required_fields)
            confidence_for_cards = confidence_ok and not low_confidence_block

            prefs_snapshot = _merge_pref_values(prefs_current, pref_updates)
            filled_slots = _build_filled_slots(query_tags, prefs_snapshot, pref_updates)
            state_intent = infer_state_intent(
                intent_text,
                product_intent=product_intent,
                support_intent=support_intent,
                order_intent=order_intent,
            )
            if router_intent == "store_info":
                state_intent = "store_info"
            elif router_intent == "complaint_support":
                state_intent = "support"
            elif router_intent == "order_intent":
                state_intent = "order_flow"
            elif router_intent == "product_link_request" and selected_product_state:
                state_intent = "product_selected"
            if selected_product_state:
                state_intent = "product_selected"
            state_category = (
                router_category
                if router_category and router_category != "unknown"
                else infer_state_category(query_text)
            )
            state_required_slots = required_fields if required_fields else None
            allow_generic_slots = bool(
                state_intent == "product_search"
                and state_category in {"shoes", "apparel"}
                and any(field in {"gender", "size", "style", "budget"} for field in required_fields)
            )
            if selected_product_state:
                allow_generic_slots = False
            remembered_profile, memory_changed = _remember_user_context(
                user.profile_json if isinstance(user.profile_json, dict) else None,
                user_text=intent_text,
                matched_products=matched_products_for_llm,
                selected_product=selected_product_state
                if isinstance(selected_product_state, dict)
                else None,
            )
            if memory_changed:
                user.profile_json = remembered_profile
            conversation_state_payload = await _touch_state(
                state_intent,
                category=state_category,
                required_slots=state_required_slots,
                filled_slots=filled_slots,
                selected_product=selected_product_state,
            )
            await log_event(
                session,
                level="info",
                event_type="intent_detected",
                data={
                    "conversation_id": conversation.id,
                    "user_id": user.id,
                    "intent": state_intent,
                    "category": state_category,
                    "router_intent": router_intent,
                    "router_category": router_category,
                    "router_confidence": router_confidence,
                    "router_evidence": router_evidence,
                    "router_risk": router_risk,
                },
                commit=False,
            )
            if required_fields:
                await log_event(
                    session,
                    level="info",
                    event_type="slots_needed",
                    data={
                        "conversation_id": conversation.id,
                        "user_id": user.id,
                        "required_slots": required_fields,
                        "filled_slots": filled_slots,
                    },
                    commit=False,
                )
            await session.commit()

            if (
                matched_products
                and (product_intent or needs_details or wants_products)
                and low_confidence_block
            ):
                await send_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    required_question_text
                    or "برای معرفی دقیق‌تر، لطفاً جنسیت، سایز، سبک (رسمی/اسپرت) و بازه قیمت رو بگید.",
                    meta=_merge_meta({
                        "source": "product_match",
                        "intent": "need_details",
                        "product_ids": matched_product_ids,
                        "product_slugs": matched_product_slugs,
                        "confidence_ok": False,
                        "match_debug": match_debug,
                        "query_tags": query_tags_meta,
                    }),
                )
                return

            if matched_products and not store_intent and (confidence_for_cards or is_plain_list_request):
                cross_sell_allowed = bool(
                    (order_intent or (behavior_match and behavior_match.pattern == "ready_to_buy"))
                    and confidence_ok
                    and not low_confidence_block
                )
                products_for_plan = await _maybe_add_cross_sell(
                    session,
                    user,
                    matched_products,
                    allow=cross_sell_allowed,
                )
                product_plan = build_product_plan(query_text, products_for_plan)
                if product_plan:
                    plan_ids = [product.id for product in products_for_plan]
                    plan_slugs = [product.slug for product in products_for_plan if product.slug]
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        product_plan,
                        meta=_merge_meta({
                            "source": "product_match",
                            "intent": "product_suggest",
                            "product_ids": plan_ids,
                            "product_slugs": plan_slugs,
                            "confidence_ok": confidence_ok,
                            "match_debug": match_debug,
                            "query_tags": query_tags_meta,
                        }),
                    )
                    if _should_schedule_followup(
                        behavior_match,
                        order_intent,
                        product_intent,
                        matched_products,
                    ):
                        await schedule_followup_task(
                            session,
                            conversation,
                            user,
                            reason="product_suggest",
                            payload={"text": "اگر سوال یا سفارش داشتید، من در خدمتم."},
                        )
                    if (wants_products or is_plain_list_request) and more_results_available:
                        await send_plan_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            _build_more_products_plan(),
                            meta=_merge_meta({
                                "source": "product_match",
                                "intent": "product_more",
                                "product_ids": matched_product_ids,
                                "product_slugs": matched_product_slugs,
                            }),
                        )
                    await _update_product_state(
                        session,
                        user,
                        query_text,
                        len(matched_products),
                        len(matched_products_for_llm),
                    )
                    return
            if product_intent and not matched_products:
                await send_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    "برای معرفی دقیق‌تر، لطفاً جنسیت، سایز، سبک (رسمی/اسپرت) و بازه قیمت رو بگید؛ اگر مدل خاصی دارید اسم یا عکسش رو بفرستید.",
                    meta=_merge_meta({"source": "product_match", "intent": "no_match"}),
                )
                return

            if not llm_first_all:
                if (intent_text or analysis_text) and _is_low_signal(intent_text or analysis_text):
                    if not (
                        is_greeting(lowered)
                        or wants_products
                        or needs_details
                        or wants_website(lowered)
                        or wants_address(lowered)
                        or wants_hours(lowered)
                        or wants_phone(lowered)
                        or wants_trust(lowered)
                    ):
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            fallback_for_message_type("text"),
                            meta=_merge_meta({"source": "guardrails", "intent": "low_signal"}),
                        )
                        return

                rule_plan = build_rule_based_plan(
                    normalized.message_type,
                    intent_text,
                    is_first_message,
                )
                if rule_plan:
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        rule_plan,
                        meta=_merge_meta({"source": "guardrails", "intent": "rule_based"}),
                    )
                    return

            if behavior_match and behavior_match.pattern == "ready_to_buy":
                current_score = user.vip_score or 0
                user.vip_score = current_score + 1
                if user.vip_score >= settings.VIP_SCORE_THRESHOLD:
                    user.is_vip = True
                await session.commit()
                if user.is_vip and current_score < settings.VIP_SCORE_THRESHOLD:
                    await log_event(
                        session,
                        level="info",
                        event_type="vip_promoted",
                        data={
                            "user_id": user.id,
                            "conversation_id": conversation.id,
                            "vip_score": user.vip_score,
                        },
                    )

                faqs = await get_verified_faqs(session)
                if normalized.text and faqs:
                    faq_answer = match_faq(normalized.text, faqs)
                    if faq_answer:
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            faq_answer,
                            meta=_merge_meta({"source": "faq", "intent": "faq_match"}),
                        )
                        return
            else:
                faqs = await get_verified_faqs(session)

            campaigns = await get_active_campaigns(session)
            policy_memory_items = await get_admin_policy_memory(session, limit=10)
            llm_products = matched_products_for_llm if should_match_products else []
            response_logs = await get_recent_response_logs(
                session,
                conversation.id,
                settings.RESPONSE_LOG_CONTEXT_LIMIT,
            )
            response_log_summary = build_response_log_summary(response_logs)
            system_notes: list[str] = []
            if analysis_text:
                detail_lines = [analysis_text]
                if analysis_payload:
                    attrs = analysis_payload.get("attributes") or {}
                    if isinstance(attrs, dict):
                        attr_bits = [
                            f"{key}:{value}"
                            for key, value in attrs.items()
                            if isinstance(value, str) and value.strip()
                        ]
                        if attr_bits:
                            detail_lines.append("مشخصات: " + "، ".join(attr_bits))
                    tags = analysis_payload.get("tags") or {}
                    if isinstance(tags, dict):
                        tag_bits = []
                        for key in ("categories", "genders", "styles", "materials", "colors", "sizes"):
                            values = tags.get(key)
                            if isinstance(values, list) and values:
                                tag_bits.append(f"{key}={', '.join(str(v) for v in values)}")
                        if tag_bits:
                            detail_lines.append("برچسب‌ها: " + " | ".join(tag_bits))
                    search_terms = analysis_payload.get("search_terms")
                    if isinstance(search_terms, list):
                        term_bits = [
                            str(term).strip()
                            for term in search_terms
                            if isinstance(term, str) and str(term).strip()
                        ]
                        if term_bits:
                            detail_lines.append("کلیدواژه‌ها: " + " | ".join(term_bits[:8]))
                system_notes.append("[IMAGE_ANALYSIS]\n" + "\n".join(detail_lines))
            if order_hint_text:
                system_notes.append(
                    "[ORDER_FLOW]\n"
                    f"کاربر در جریان ثبت سفارش است. لطفاً همین پیام را ارسال کن:\n{order_hint_text}\n"
                    "تا زمانی که این مرحله کامل نشده، پیشنهاد محصول نده."
                )
            if low_confidence_block and required_question_text:
                system_notes.append(
                    "[NEED_DETAILS]\n"
                    f"اعتماد پایین است. قبل از پیشنهاد محصول این سؤال را بپرس:\n{required_question_text}\n"
                    "تا جزئیات کامل نشده، محصول پیشنهاد نده."
                )
            policy_memory_text = format_admin_policy_memory(policy_memory_items)
            if policy_memory_text:
                system_notes.append(
                    "[ADMIN_POLICY_MEMORY - HIGH PRIORITY]\n"
                    f"{policy_memory_text}\n"
                    "قانون اجرایی: اگر پاسخ با این سیاست‌ها تضاد داشت، مطابق همین سیاست‌ها پاسخ بده."
                )
            allow_product_cards = bool(
                matched_products
                and not low_confidence_block
                and not order_hint_text
                and (product_intent or wants_products or needs_details or visual_product_intent)
            )
            llm_messages = build_llm_messages(
                history,
                bot_settings,
                normalized,
                user,
                llm_products,
                campaigns=campaigns,
                faqs=faqs,
                catalog_summary=catalog_summary,
                behavior_snapshot=behavior_snapshot,
                conversation_state=conversation_state_payload,
                response_log_summary=response_log_summary,
                system_notes=system_notes,
                admin_notes=bot_settings.admin_notes if bot_settings else None,
                allow_product_cards=allow_product_cards,
            )
            await log_event(
                session,
                level="info",
                event_type="context_built",
                data={
                    "conversation_id": conversation.id,
                    "user_id": user.id,
                    "product_context_count": len(llm_products),
                    "campaign_count": len(campaigns),
                    "faq_count": len(faqs),
                    "has_state": bool(conversation_state_payload),
                    "has_behavior": bool(behavior_snapshot),
                },
                commit=False,
            )
            await session.commit()

            provider = choose_provider(
                normalized, bot_settings.ai_mode if bot_settings else None
            )
            logger.info("provider_selected", provider=provider)
            await log_event(
                session,
                level="info",
                event_type="provider_selected",
                data={"provider": provider, "sender_id": normalized.sender_id},
                commit=False,
            )
            start_time = time.monotonic()
            provider_used = None

            try:
                reply_text, usage, provider_used = await generate_with_fallback(
                    provider, llm_messages
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "llm_latency_ms",
                    provider=provider_used,
                    latency_ms=latency_ms,
                )
                await log_event(
                    session,
                    level="info",
                    event_type="llm_latency",
                    data={"provider": provider_used, "latency_ms": latency_ms},
                    commit=False,
                )
                max_chars = (
                    bot_settings.max_output_chars
                    if bot_settings and bot_settings.max_output_chars
                    else settings.MAX_RESPONSE_CHARS
                )
                fallback_text = (
                    bot_settings.fallback_text
                    if bot_settings and bot_settings.fallback_text
                    else _build_contextual_reply(
                        user=user,
                        query_text=query_text,
                        analysis_text=analysis_text,
                        matched_products=matched_products,
                        wants_products=wants_products,
                        needs_details=needs_details,
                    )
                )
                reply_text = post_process(reply_text, max_chars=max_chars, fallback_text=fallback_text)
                await record_usage(session, usage, provider_used)
            except LLMError as exc:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(
                    "errors",
                    stage="llm",
                    error=str(exc),
                    latency_ms=latency_ms,
                )
                await log_event(
                    session,
                    level="error",
                    event_type="llm_error",
                    message=str(exc),
                    data={"latency_ms": latency_ms},
                )
                reply_text = (
                    bot_settings.fallback_text
                    if bot_settings and bot_settings.fallback_text
                    else _build_contextual_reply(
                        user=user,
                        query_text=query_text,
                        analysis_text=analysis_text,
                        matched_products=matched_products,
                        wants_products=wants_products,
                        needs_details=needs_details,
                    )
                )

            show_products = False
            auto_show_products = allow_product_cards
            token_requested = False
            if reply_text:
                token_requested, reply_text = _split_show_products(reply_text)
            if allow_product_cards and token_requested:
                show_products = True
            if allow_product_cards and llm_first_all and auto_show_products and not show_products:
                show_products = True
            if (
                allow_product_cards
                and matched_products
                and not show_products
                and (visual_product_intent or wants_products or product_intent or needs_details)
            ):
                show_products = True

            if order_hint_text:
                reply_text = order_hint_text
                show_products = False
            elif required_question_text and not _contains_required_fields(reply_text, required_fields):
                reply_text = required_question_text
                show_products = False
            elif product_intent and not matched_products and needs_product_details(reply_text):
                reply_text = build_product_details_question()
                show_products = False
            elif (
                settings.LLM_STRICT_PRICE_GROUNDING
                and (product_intent or needs_details or wants_products or selected_product_state)
            ):
                selected_payload = (
                    selected_product_state if isinstance(selected_product_state, dict) else None
                )
                allowed_prices = _allowed_price_values(llm_products, selected_payload)
                if _reply_has_ungrounded_price(reply_text, allowed_prices):
                    reply_text = "برای اعلام قیمت دقیق، لطفاً اسم/مدل یا لینک همون محصول رو بفرستید."
                    show_products = False
                    await log_event(
                        session,
                        level="info",
                        event_type="hallucination_prevented",
                        data={
                            "conversation_id": conversation.id,
                            "user_id": user.id,
                            "reason": "price_not_grounded_in_context",
                            "allowed_prices": sorted(allowed_prices)[:10],
                        },
                        commit=False,
                    )

            guardrail_blocked_products = False
            product_plan = None
            products_for_plan = matched_products
            if show_products and matched_products:
                cross_sell_allowed = bool(
                    (order_intent or (behavior_match and behavior_match.pattern == "ready_to_buy"))
                    and confidence_ok
                    and not low_confidence_block
                )
                products_for_plan = await _maybe_add_cross_sell(
                    session,
                    user,
                    matched_products,
                    allow=cross_sell_allowed,
                )
                product_plan = build_product_plan(query_text, products_for_plan)

            if show_products and not reply_text:
                reply_text = "چند پیشنهاد مرتبط برات آماده کردم:"

            if not reply_text:
                reply_text = (
                    bot_settings.fallback_text
                    if bot_settings and bot_settings.fallback_text
                    else _build_contextual_reply(
                        user=user,
                        query_text=query_text,
                        analysis_text=analysis_text,
                        matched_products=matched_products,
                        wants_products=wants_products,
                        needs_details=needs_details,
                    )
                )

            if reply_text:
                rewrite_reasons: list[str] = []
                allow_question = bool(
                    order_hint_text
                    or low_confidence_block
                    or product_intent
                    or needs_details
                )
                max_questions = 1 if allow_question else 0
                reply_text = _limit_questions(reply_text, max_questions)
                reply_text = _limit_sentences(
                    reply_text, settings.MAX_RESPONSE_SENTENCES
                )
                reply_text = _limit_emojis(reply_text, 1)
                if normalized.media_url and _looks_like_image_blind_reply(reply_text):
                    rewrite_reasons.append("image_blind_reply_rewritten")
                    if matched_products:
                        reply_text = "این مدل رو بررسی کردم؛ چند گزینه نزدیک پیدا شد. رنگ/سایز مدنظرتون رو بگید تا دقیق‌تر بفرستم."
                        show_products = True
                    else:
                        reply_text = "تصویر دریافت شد. برای اعلام دقیق قیمت و موجودی، اسم مدل یا رنگ مدنظرتون رو بفرستید."
                if _looks_like_generic_assistant_reply(reply_text):
                    rewrite_reasons.append("generic_reply_rewritten")
                    reply_text = _build_contextual_reply(
                        user=user,
                        query_text=query_text,
                        analysis_text=analysis_text,
                        matched_products=matched_products,
                        wants_products=wants_products,
                        needs_details=needs_details,
                    )
                    if allow_product_cards and matched_products:
                        show_products = True
                loop_reference: str | None = None
                loop_reason: str | None = None
                if last_assistant_text and _is_repetitive_reply(reply_text, last_assistant_text):
                    loop_reference = last_assistant_text
                    loop_reason = "loop_repeated_last_reply"
                elif (
                    len(recent_assistant_texts) >= 2
                    and _is_repetitive_reply(reply_text, recent_assistant_texts[1])
                ):
                    loop_reference = recent_assistant_texts[1]
                    loop_reason = "loop_repeated_recent_cycle"
                if loop_reference:
                    if loop_reason:
                        rewrite_reasons.append(loop_reason)
                    loop_payload = await _touch_state(
                        state.intent or "unknown",
                        category=state.category or infer_state_category(query_text),
                        required_slots=state.slots_required,
                        filled_slots=state.slots_filled,
                        selected_product=selected_product_state,
                        preserve_selected_product=True,
                        last_handler_used="loop_detected",
                        increment_loop=True,
                    )
                    loop_count = 0
                    if isinstance(loop_payload, dict):
                        loop_count = int(loop_payload.get("loop_counter") or 0)
                    await log_event(
                        session,
                        level="info",
                        event_type="loop_detected",
                        data={
                            "conversation_id": conversation.id,
                            "user_id": user.id,
                            "reply_text": reply_text,
                            "last_reply": loop_reference,
                            "reason": loop_reason,
                            "loop_counter": loop_count,
                        },
                        commit=False,
                    )
                    if low_confidence_block and required_fields:
                        reply_text = _format_required_question_alt(required_fields, required_known)
                    elif store_intent:
                        reply_text = "باشه، همین اطلاعات رو دوباره برات می‌فرستم."
                    elif product_intent:
                        reply_text = "چند گزینه نزدیک پیدا کردم؛ اگر جزئیات بیشتری داری بگو تا دقیق‌تر بفرستم."
                    else:
                        reply_text = "متوجه شدم؛ اگر جزئیات بیشتری داری بفرست تا بهتر راهنمایی کنم."
                    if loop_count >= settings.LOOP_BREAKER_THRESHOLD:
                        if store_intent:
                            reply_text = "برای اینکه دقیق جواب بدم، بفرمایید دنبال کدوم اطلاعات فروشگاه هستید؟"
                        elif support_intent:
                            reply_text = build_angry_response()
                        else:
                            reply_text = "حق با شماست، اشتباه شد. اسم دقیق مدل یا یه عکس از محصول رو می‌فرستید؟"
                    escalated_ticket = None
                    if settings.LOOP_AUTO_ESCALATE_ENABLED:
                        escalated_ticket = await auto_escalate_loop_to_operator(
                            session,
                            user_id=user.id,
                            conversation_id=conversation.id,
                            loop_counter=loop_count,
                            threshold=settings.LOOP_ESCALATION_THRESHOLD,
                            cooldown_minutes=settings.LOOP_ESCALATION_COOLDOWN_MIN,
                            reason=loop_reason or "loop_detected",
                            last_message=intent_text,
                        )
                    if escalated_ticket:
                        rewrite_reasons.append("auto_escalated_to_operator")
                        reply_text = (
                            "برای جلوگیری از تکرار، گفتگو به اپراتور ارجاع شد. "
                            "همکار پشتیبانی خیلی زود ادامه می‌دهد."
                        )
                        show_products = False
                        product_plan = None
                    reply_text = _limit_questions(reply_text, max_questions)
                    reply_text = _limit_sentences(
                        reply_text, settings.MAX_RESPONSE_SENTENCES
                    )
                    reply_text = _limit_emojis(reply_text, 1)
                guardrail_plan, guardrail_reasons = validate_reply_or_rewrite(
                    OutboundPlan(type="text", text=reply_text),
                    conversation_state_payload,
                    intent_text,
                    has_products_context=bool(llm_products),
                    allow_generic_slots=allow_generic_slots,
                )
                reply_text = guardrail_plan.text or reply_text
                if guardrail_reasons:
                    rewrite_reasons.extend(guardrail_reasons)

                rewrite_reasons = list(dict.fromkeys(rewrite_reasons))
                if rewrite_reasons:
                    guardrail_blocked_products = any(
                        reason.startswith(("link_request", "template_blocked", "hallucination_prevented"))
                        for reason in rewrite_reasons
                    )
                    if guardrail_blocked_products:
                        show_products = False
                        product_plan = None
                    await log_event(
                        session,
                        level="info",
                        event_type="reply_rewritten_by_guardrail",
                        data={
                            "conversation_id": conversation.id,
                            "user_id": user.id,
                            "reasons": rewrite_reasons,
                            "reply_text": reply_text,
                        },
                        commit=False,
                    )
                    for reason in rewrite_reasons:
                        if reason.startswith("template_blocked"):
                            await log_event(
                                session,
                                level="info",
                                event_type="template_blocked",
                                data={
                                    "conversation_id": conversation.id,
                                    "user_id": user.id,
                                    "reason": reason,
                                },
                                commit=False,
                            )
                        elif reason.startswith("hallucination_prevented"):
                            await log_event(
                                session,
                                level="info",
                                event_type="hallucination_prevented",
                                data={
                                    "conversation_id": conversation.id,
                                    "user_id": user.id,
                                    "reason": reason,
                                },
                                commit=False,
                            )
                        elif reason.startswith("link_request"):
                            await log_event(
                                session,
                                level="info",
                                event_type="link_request_handled",
                                data={
                                    "conversation_id": conversation.id,
                                    "user_id": user.id,
                                    "reason": reason,
                                },
                                commit=False,
                            )
                    await session.commit()
                await send_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    reply_text,
                    meta=_merge_meta({
                        "source": "llm",
                        "intent": "llm",
                        "provider": provider_used,
                        "product_context_count": len(llm_products),
                        "product_ids": matched_product_ids,
                        "product_slugs": matched_product_slugs,
                        "catalog_used": bool(catalog_summary),
                        "response_logs_used": bool(response_log_summary),
                        "llm_first": llm_first_all,
                        "confidence_ok": confidence_ok,
                        "low_confidence": low_confidence,
                        "required_fields": required_fields,
                        "order_flow": bool(order_hint_text),
                        "show_products_token": show_products,
                        "match_debug": match_debug,
                        "query_tags": query_tags_meta,
                    }),
                )
                if order_hint_text and not product_plan:
                    await schedule_followup_task(
                        session,
                        conversation,
                        user,
                        reason="order_flow",
                        payload={"text": order_hint_text},
                    )

            if product_plan:
                plan_ids = []
                plan_slugs = []
                if products_for_plan:
                    plan_ids = [product.id for product in products_for_plan]
                    plan_slugs = [product.slug for product in products_for_plan if product.slug]
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    product_plan,
                    meta=_merge_meta({
                        "source": "product_match",
                        "intent": "product_suggest",
                        "product_ids": plan_ids or matched_product_ids,
                        "product_slugs": plan_slugs or matched_product_slugs,
                        "confidence_ok": confidence_ok,
                        "llm_first": llm_first_all,
                        "match_debug": match_debug,
                        "query_tags": query_tags_meta,
                    }),
                )
                if _should_schedule_followup(
                    behavior_match,
                    order_intent,
                    product_intent,
                    matched_products,
                ):
                    await schedule_followup_task(
                        session,
                        conversation,
                        user,
                        reason="product_suggest",
                        payload={"text": "اگر سوال یا سفارش داشتید، من در خدمتم."},
                    )
                if (wants_products or is_plain_list_request) and more_results_available:
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        _build_more_products_plan(),
                        meta=_merge_meta({
                            "source": "product_match",
                            "intent": "product_more",
                            "product_ids": matched_product_ids,
                            "product_slugs": matched_product_slugs,
                        }),
                    )
                await _update_product_state(
                    session,
                    user,
                    query_text,
                    len(matched_products),
                    len(matched_products_for_llm),
                )
        except Exception as exc:
            logger.error("errors", stage="processor", error=str(exc))
            await session.rollback()


async def upsert_user(session: AsyncSession, message: NormalizedMessage) -> User:
    result = await session.execute(
        select(User).where(User.external_id == message.sender_id)
    )
    user = result.scalars().first()
    if user:
        if message.username:
            user.username = message.username
        if message.follow_status:
            user.follow_status = message.follow_status
        if message.follower_count is not None:
            user.follower_count = message.follower_count
        return user

    user = User(
        external_id=message.sender_id,
        username=message.username,
        follow_status=message.follow_status,
        follower_count=message.follower_count,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_conversation(session: AsyncSession, user_id: int) -> Conversation:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.status == "open")
        .order_by(Conversation.created_at.desc())
    )
    conversation = result.scalars().first()
    if conversation:
        return conversation

    conversation = Conversation(user_id=user_id, status="open")
    session.add(conversation)
    await session.flush()
    return conversation


async def save_message(
    session: AsyncSession,
    conversation_id: int,
    message: NormalizedMessage,
    role: str,
) -> Message:
    content_text = message.text
    if message.message_type == "read" and message.read_message_id:
        content_text = message.read_message_id
    record = Message(
        conversation_id=conversation_id,
        role=role,
        type=message.message_type,
        content_text=content_text,
        media_url=message.media_url or message.audio_url,
        payload_json=message.raw_payload,
    )
    session.add(record)
    await session.flush()
    return record


async def get_active_bot_settings(session: AsyncSession) -> BotSettings | None:
    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    settings_record = result.scalars().first()
    if settings_record:
        return settings_record

    system_prompt = load_prompt("system.txt")
    settings_record = BotSettings(
        ai_mode=settings.LLM_MODE,
        system_prompt=system_prompt,
        max_history_messages=settings.MAX_HISTORY_MESSAGES,
        max_output_chars=settings.MAX_RESPONSE_CHARS,
        language=settings.DEFAULT_LANGUAGE,
        active=True,
    )
    session.add(settings_record)
    await session.commit()
    return settings_record


async def get_recent_history(
    session: AsyncSession, conversation_id: int, limit: int
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_recent_response_logs(
    session: AsyncSession,
    conversation_id: int,
    limit: int,
) -> list[AppLog]:
    if limit <= 0:
        return []
    result = await session.execute(
        select(AppLog)
        .where(AppLog.event_type == "assistant_response")
        .where(cast(AppLog.data["conversation_id"].astext, Integer) == conversation_id)
        .order_by(AppLog.created_at.desc())
        .limit(limit)
    )
    logs = list(result.scalars().all())
    logs.reverse()
    return logs


def build_response_log_summary(logs: list[AppLog]) -> str | None:
    if not logs:
        return None
    lines: list[str] = []
    for log in logs:
        message = (log.message or "").strip()
        if not message:
            continue
        data = log.data or {}
        source = data.get("source", "reply")
        intent = data.get("intent")
        tag = source if not intent else f"{source}/{intent}"
        snippet = " ".join(message.split())
        if len(snippet) > settings.LLM_MESSAGE_MAX_CHARS:
            snippet = snippet[: settings.LLM_MESSAGE_MAX_CHARS].rstrip() + "..."
        lines.append(f"- [{tag}] {snippet}")
    if not lines:
        return None
    summary = "[RECENT_RESPONSES]\n" + "\n".join(lines)
    if len(summary) > settings.LLM_MESSAGE_MAX_CHARS:
        summary = summary[: settings.LLM_MESSAGE_MAX_CHARS].rstrip() + "..."
    return summary


def _trim_history_for_llm(
    history: list[Message], max_user_turns: int
) -> list[Message]:
    if max_user_turns <= 0:
        return history
    trimmed: list[Message] = []
    user_turns = 0
    for msg in reversed(history):
        trimmed.append(msg)
        if msg.role == "user" and msg.type != "read":
            user_turns += 1
            if user_turns >= max_user_turns:
                break
    trimmed.reverse()
    return trimmed


async def get_verified_faqs(session: AsyncSession, limit: int = 30) -> list[Faq]:
    result = await session.execute(
        select(Faq)
        .where(Faq.verified.is_(True))
        .order_by(Faq.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_active_campaigns(session: AsyncSession, limit: int = 5) -> list[Campaign]:
    now = utc_now()
    query = (
        select(Campaign)
        .where(Campaign.active.is_(True))
        .where((Campaign.start_at.is_(None)) | (Campaign.start_at <= now))
        .where((Campaign.end_at.is_(None)) | (Campaign.end_at >= now))
        .order_by(Campaign.priority.desc(), Campaign.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


def match_faq(text: str, faqs: list[Faq]) -> str | None:
    normalized = text.strip().lower()
    for faq in faqs:
        if faq.question and faq.question.strip().lower() in normalized:
            return faq.answer
        if faq.tags:
            for tag in faq.tags:
                if tag and tag.strip().lower() in normalized and len(tag) >= FAQ_MATCH_MIN_LEN:
                    return faq.answer
    return None


def inject_campaigns_and_faqs(
    messages: list[dict[str, str]],
    campaigns: list[Campaign],
    faqs: list[Faq],
) -> list[dict[str, str]]:
    additions: list[str] = []
    if campaigns:
        lines = []
        for campaign in campaigns:
            parts = [campaign.title, campaign.body]
            if campaign.discount_code:
                parts.append(f"کد تخفیف: {campaign.discount_code}")
            if campaign.link:
                parts.append(f"لینک: {campaign.link}")
            lines.append(" | ".join(part for part in parts if part))
        additions.append("کمپین‌های فعال:\n" + "\n".join(f"- {line}" for line in lines))
    if faqs:
        faq_lines = [
            f"Q: {faq.question}\nA: {faq.answer}" for faq in faqs if faq.question and faq.answer
        ]
        if faq_lines:
            additions.append("FAQ تاییدشده:\n" + "\n".join(faq_lines))
    if not additions:
        return messages
    return messages + [{"role": "system", "content": "\n\n".join(additions)}]


def build_llm_messages(
    history: list[Message],
    bot_settings: BotSettings | None,
    message: NormalizedMessage,
    user: User,
    products: list[Product] | None = None,
    campaigns: list[Campaign] | None = None,
    faqs: list[Faq] | None = None,
    catalog_summary: str | None = None,
    behavior_snapshot: dict[str, Any] | None = None,
    conversation_state: dict[str, Any] | None = None,
    response_log_summary: str | None = None,
    system_notes: list[str] | None = None,
    admin_notes: str | None = None,
    allow_product_cards: bool = False,
) -> list[dict[str, str]]:
    history = _trim_history_for_llm(history, settings.LLM_MAX_USER_TURNS)
    base_prompt = bot_settings.system_prompt if bot_settings else load_prompt("system.txt")
    store_knowledge = get_store_knowledge_text()

    prompt_parts = [base_prompt]
    if message.text:
        lowered = message.text.lower()
        if any(keyword in lowered for keyword in SALES_KEYWORDS):
            prompt_parts.append(load_prompt("sales.txt"))
        if any(keyword in lowered for keyword in SUPPORT_KEYWORDS):
            prompt_parts.append(load_prompt("support.txt"))

    from app.services.context_bundle import build_context_bundle

    bundle = build_context_bundle(
        base_prompt="\n\n".join(part for part in prompt_parts if part).strip(),
        store_text=store_knowledge,
        campaigns=campaigns or [],
        faqs=faqs or [],
        catalog_summary=catalog_summary,
        behavior_snapshot=behavior_snapshot,
        conversation_state=conversation_state,
        recent_messages=history,
        user=user,
        admin_notes=admin_notes,
        response_log_summary=response_log_summary,
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": bundle.system_prompt}]

    if system_notes:
        for note in system_notes:
            if note:
                messages.append({"role": "system", "content": note})

    if products:
        product_lines: list[str] = []
        for product in products:
            title = product.title or product.slug or "بدون عنوان"
            price = str(product.price) if product.price is not None else "نامشخص"
            old_price = (
                str(product.old_price) if product.old_price is not None else None
            )
            availability = (
                product.availability.value
                if hasattr(product.availability, "value")
                else str(product.availability)
            )
            product_tags = infer_tags(
                " ".join(
                    part
                    for part in [
                        product.slug,
                        product.title,
                        product.description,
                        product.product_id,
                    ]
                    if part
                )
            )
            parts = [title, f"قیمت: {price}"]
            if old_price:
                parts.append(f"قبل: {old_price}")
            parts.append(f"موجودی: {availability}")
            if product.product_id:
                parts.append(f"مدل: {product.product_id}")
            if product_tags.categories:
                parts.append(f"دسته: {', '.join(product_tags.categories)}")
            if product_tags.genders:
                parts.append(f"جنسیت: {', '.join(product_tags.genders)}")
            if product_tags.materials:
                parts.append(f"جنس: {', '.join(product_tags.materials)}")
            if product_tags.styles:
                parts.append(f"سبک: {', '.join(product_tags.styles)}")
            if product_tags.colors:
                parts.append(f"رنگ: {', '.join(product_tags.colors[:3])}")
            if product.description:
                description = " ".join(product.description.split())
                if description:
                    parts.append(f"توضیحات: {description[:260]}")
            if isinstance(product.images, list):
                image_urls = [
                    str(item).strip()
                    for item in product.images
                    if isinstance(item, str) and str(item).strip()
                ]
                if image_urls:
                    parts.append(f"عکس‌ها: {', '.join(image_urls[:2])}")
            if product.page_url:
                parts.append(f"لینک: {product.page_url}")
            product_lines.append(" | ".join(parts))
        product_context = (
            "[PRODUCTS]\n"
            + "\n".join(f"- {line}" for line in product_lines)
            + "\nRules:\n"
            "- فقط از قیمت‌های بالا استفاده کن و قیمت جدید نساز.\n"
            "- اگر قیمت نامشخص بود، همین را اعلام کن و از کاربر جزئیات بپرس."
        )
        if allow_product_cards:
            product_context += (
                "\n- اگر می‌خواهی کارت محصول نمایش داده شود، دقیقاً یک خط جدا شامل "
                f"{SHOW_PRODUCTS_TOKEN} بنویس."
            )
        messages.append({"role": "system", "content": product_context})

    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        if item.type == "read":
            continue
        content = item.content_text
        if not content:
            content = f"[{item.type.upper()}]"
        messages.append({"role": item.role, "content": content})

    return messages


async def generate_with_fallback(
    primary_provider: str, messages: list[dict[str, str]]
) -> tuple[str, dict, str]:
    providers = [primary_provider]
    fallback = "deepseek" if primary_provider == "openai" else "openai"
    if fallback not in providers:
        providers.append(fallback)

    last_error: Exception | None = None
    for provider in providers:
        try:
            reply_text, usage = await generate_reply(provider, messages)
            return reply_text, usage, provider
        except LLMError as exc:
            last_error = exc
            logger.warning("provider_failed", provider=provider)

    raise LLMError(f"All providers failed: {last_error}")


async def record_usage(session: AsyncSession, usage: dict | None, provider: str) -> None:
    tokens_in = usage.get("prompt_tokens") if usage else None
    tokens_out = usage.get("completion_tokens") if usage else None
    record = Usage(
        date=utc_now().date(),
        provider=provider,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=None,
    )
    session.add(record)
    await session.commit()


async def within_window(session: AsyncSession, conversation_id: int) -> bool:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation or not conversation.last_user_message_at:
        return False
    delta = utc_now() - conversation.last_user_message_at
    return delta.total_seconds() <= settings.WINDOW_HOURS * 3600


async def send_and_store(
    session: AsyncSession,
    conversation_id: int,
    receiver_id: str,
    text: str,
    meta: dict | None = None,
) -> None:
    plan = plan_outbound(text)
    await send_plan_and_store(session, conversation_id, receiver_id, plan, meta=meta)


async def send_plan_and_store(
    session: AsyncSession,
    conversation_id: int,
    receiver_id: str,
    plan: OutboundPlan,
    meta: dict | None = None,
) -> str | None:
    def _plan_to_text(value: OutboundPlan) -> str:
        if value.text:
            return value.text
        if value.type == "generic_template":
            lines = []
            for element in value.elements:
                line = element.title
                if element.subtitle:
                    line = f"{line} - {element.subtitle}"
                lines.append(line)
            if lines:
                return "\n".join(lines)
        return fallback_for_message_type("text")

    if not await within_window(session, conversation_id):
        logger.info(
            "window_expired",
            receiver_id=receiver_id,
            conversation_id=conversation_id,
        )
        await log_event(
            session,
            level="info",
            event_type="window_expired",
            message="24h window expired",
            data={"receiver_id": receiver_id, "conversation_id": conversation_id},
        )
        return None

    if plan.type in {"text", "button", "quick_reply"} and not plan.text:
        plan.text = fallback_for_message_type("text")
    if plan.type == "generic_template" and not plan.elements:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.type == "photo" and not plan.image_url:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.type == "video" and not plan.video_url:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.type == "audio" and not plan.audio_url:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")

    if plan.type == "button":
        plan.buttons = plan.buttons[: settings.MAX_BUTTONS]
        plan.buttons = [
            button
            for button in plan.buttons
            if button.title and (button.url or button.payload)
        ]
        if not plan.buttons:
            plan.type = "text"
            plan.text = plan.text or fallback_for_message_type("text")
    if plan.type == "quick_reply":
        cleaned_replies = []
        for option in plan.quick_replies[: settings.MAX_QUICK_REPLIES]:
            option.title = option.title[: settings.QUICK_REPLY_TITLE_MAX_CHARS].strip()
            option.payload = option.payload[: settings.QUICK_REPLY_PAYLOAD_MAX_CHARS].strip()
            if not option.title or not option.payload:
                continue
            cleaned_replies.append(option)
        plan.quick_replies = cleaned_replies
        if not plan.quick_replies:
            plan.type = "text"
            plan.text = plan.text or fallback_for_message_type("text")
    if plan.type == "generic_template":
        cleaned_elements = []
        for element in plan.elements[: settings.MAX_TEMPLATE_SLIDES]:
            element.title = element.title[:80].strip()
            if not element.title:
                continue
            if element.subtitle:
                element.subtitle = element.subtitle[:80].strip()
            element.buttons = element.buttons[: settings.MAX_BUTTONS]
            cleaned_elements.append(element)
        plan.elements = cleaned_elements
        if not plan.elements:
            plan.type = "text"
            plan.text = fallback_for_message_type("text")

    guardrail_reasons: list[str] = []
    if conversation_id:
        state = await get_or_create_state(session, conversation_id)
        state_payload = build_state_payload(state)
        required_slots = (
            state.slots_required if isinstance(state.slots_required, list) else []
        )
        allow_generic_slots = bool(
            state.intent == "product_search"
            and state.category in {"shoes", "apparel"}
            and any(slot in {"gender", "size", "style", "budget"} for slot in required_slots)
        )
        has_products_context = bool(
            meta
            and (
                meta.get("product_ids")
                or meta.get("product_slugs")
                or meta.get("product_context_count")
            )
        )
        if plan.type == "generic_template":
            has_products_context = True
        guardrail_plan, guardrail_reasons = validate_reply_or_rewrite(
            plan,
            state_payload,
            state.last_user_question,
            has_products_context=has_products_context,
            allow_generic_slots=allow_generic_slots,
        )
        if guardrail_reasons:
            plan = guardrail_plan
            await log_event(
                session,
                level="info",
                event_type="reply_rewritten_by_guardrail",
                data={
                    "conversation_id": conversation_id,
                    "receiver_id": receiver_id,
                    "reasons": guardrail_reasons,
                    "plan_type": plan.type,
                },
                commit=False,
            )
            for reason in guardrail_reasons:
                if reason.startswith("template_blocked"):
                    await log_event(
                        session,
                        level="info",
                        event_type="template_blocked",
                        data={
                            "conversation_id": conversation_id,
                            "receiver_id": receiver_id,
                            "reason": reason,
                        },
                        commit=False,
                    )
                elif reason.startswith("hallucination_prevented"):
                    await log_event(
                        session,
                        level="info",
                        event_type="hallucination_prevented",
                        data={
                            "conversation_id": conversation_id,
                            "receiver_id": receiver_id,
                            "reason": reason,
                        },
                        commit=False,
                    )
                elif reason.startswith("link_request"):
                    await log_event(
                        session,
                        level="info",
                        event_type="link_request_handled",
                        data={
                            "conversation_id": conversation_id,
                            "receiver_id": receiver_id,
                            "reason": reason,
                        },
                        commit=False,
                    )
            await session.commit()

    if plan.text:
        plan.text = plan.text[: settings.MAX_RESPONSE_CHARS].strip()

    await log_event(
        session,
        level="info",
        event_type="reply_planned",
        data={
            "conversation_id": conversation_id,
            "receiver_id": receiver_id,
            "plan_type": plan.type,
            "intent": meta.get("intent") if meta else None,
            "store_topic": meta.get("store_topic") if meta else None,
        },
        commit=False,
    )

    sender = Sender()

    try:
        response_data = None
        if plan.type == "button":
            response_data = await sender.send_button_text(
                receiver_id, plan.text or "", plan.buttons
            )
        elif plan.type == "quick_reply":
            response_data = await sender.send_quick_reply(
                receiver_id, plan.text or "", plan.quick_replies
            )
        elif plan.type == "generic_template":
            response_data = await sender.send_generic_template(receiver_id, plan.elements)
        elif plan.type == "photo":
            response_data = await sender.send_photo(receiver_id, plan.image_url or "")
        elif plan.type == "video":
            response_data = await sender.send_video(receiver_id, plan.video_url or "")
        elif plan.type == "audio":
            response_data = await sender.send_audio(receiver_id, plan.audio_url or "")
        else:
            response_data = await sender.send_text(receiver_id, plan.text or "")
        message_id = None
        if isinstance(response_data, dict):
            message_id = response_data.get("message_id")
        logger.info(
            "outbound_sent",
            receiver_id=receiver_id,
            message_type=plan.type,
            message_id=message_id,
        )
        await log_event(
            session,
            level="info",
            event_type="outbound_sent",
            message=plan.text,
            data={
                "receiver_id": receiver_id,
                "message_type": plan.type,
                "message_id": message_id,
            },
            commit=False,
        )
        response_meta = {
            "receiver_id": receiver_id,
            "conversation_id": conversation_id,
            "message_type": plan.type,
            "message_id": message_id,
            "source": "unspecified",
        }
        if guardrail_reasons:
            response_meta["guardrail_reasons"] = list(guardrail_reasons)
        if meta:
            response_meta.update(meta)
        await log_event(
            session,
            level="info",
            event_type="assistant_response",
            message=plan.text,
            data=response_meta,
            commit=False,
        )
        if plan.quick_replies and plan.type != "quick_reply":
            follow_text = plan.text or "کدوم گزینه مدنظر شماست؟"
            follow_plan = OutboundPlan(
                type="quick_reply",
                text=follow_text,
                quick_replies=plan.quick_replies,
            )
            await send_plan_and_store(
                session,
                conversation_id,
                receiver_id,
                follow_plan,
                meta=meta,
            )
    except SenderError as exc:
        logger.error("errors", stage="send", error=str(exc))
        await log_event(
            session,
            level="error",
            event_type="send_error",
            message=str(exc),
            data={"receiver_id": receiver_id, "message_type": plan.type},
        )
        if plan.type == "text":
            return None
        fallback_text = _plan_to_text(plan)
        try:
            response_data = await sender.send_text(receiver_id, fallback_text)
        except SenderError:
            return None
        message_id = None
        if isinstance(response_data, dict):
            message_id = response_data.get("message_id")
        logger.info(
            "outbound_sent",
            receiver_id=receiver_id,
            message_type="text_fallback",
            message_id=message_id,
        )
        await log_event(
            session,
            level="info",
            event_type="outbound_sent",
            message=fallback_text,
            data={
                "receiver_id": receiver_id,
                "message_type": "text_fallback",
                "message_id": message_id,
            },
            commit=False,
        )
        response_meta = {
            "receiver_id": receiver_id,
            "conversation_id": conversation_id,
            "message_type": "text_fallback",
            "message_id": message_id,
            "source": "unspecified",
        }
        if guardrail_reasons:
            response_meta["guardrail_reasons"] = list(guardrail_reasons)
        if meta:
            response_meta.update(meta)
        await log_event(
            session,
            level="info",
            event_type="assistant_response",
            message=fallback_text,
            data=response_meta,
            commit=False,
        )
        plan = OutboundPlan(type="text", text=fallback_text)

    conversation = await session.get(Conversation, conversation_id)
    if conversation:
        conversation.last_bot_message_at = utc_now()

    record = Message(
        conversation_id=conversation_id,
        role="assistant",
        type=plan.type,
        content_text=plan.text,
        media_url=plan.image_url or plan.video_url or plan.audio_url,
        payload_json=plan.model_dump(),
    )
    session.add(record)
    await session.commit()
    action_key = None
    handler_used = None
    if meta and meta.get("intent"):
        action_key = str(meta["intent"])
        if meta.get("store_topic"):
            action_key = f"{action_key}:{meta['store_topic']}"
    if meta and meta.get("handler"):
        handler_used = str(meta["handler"])
    if action_key:
        await record_bot_action(
            session,
            conversation_id,
            action_key,
            _plan_to_text(plan),
            handler_used=handler_used,
        )
    return message_id
