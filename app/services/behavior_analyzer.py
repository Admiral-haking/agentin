from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.product_taxonomy import infer_tags, match_brands
from app.utils.time import utc_now

_WORD_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_ARABIC_FIX = str.maketrans({
    "ي": "ی",
    "ك": "ک",
    "‌": " ",
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


@dataclass(frozen=True)
class BehaviorMatch:
    pattern: str
    confidence: float
    reason: str
    keywords: tuple[str, ...]
    tags: tuple[str, ...]


PATTERN_RULES: dict[str, dict[str, Any]] = {
    "order_cancel": {
        "keywords": {"لغو", "کنسل", "cancel", "لغو سفارش", "انصراف"},
        "base": 0.8,
    },
    "order_followup": {
        "keywords": {
            "پیگیری",
            "پیگیری سفارش",
            "کد سفارش",
            "وضعیت سفارش",
            "رهگیری",
            "کد رهگیری",
            "مرسوله",
            "ارسال شد",
            "تحویل",
            "سفارش من",
        },
        "base": 0.75,
    },
    "purchase_intent": {
        "keywords": {
            "میخرم",
            "می خرم",
            "می‌خرم",
            "ثبت سفارش",
            "ثبت کن",
            "خرید کنم",
            "میخوام بخرم",
            "می‌خوام بخرم",
            "می‌خوام ثبت",
            "سفارش بده",
        },
        "base": 0.7,
    },
    "complaint": {
        "keywords": {
            "ناراضی",
            "افتضاح",
            "بد",
            "خرابه",
            "کیفیت بد",
            "شکایت",
            "مشکل دارم",
            "کلاهبرداری",
            "تاخیر",
            "بدقولی",
        },
        "base": 0.7,
    },
    "return_exchange": {
        "keywords": {
            "مرجوع",
            "مرجوعی",
            "بازگشت",
            "تعویض",
            "پس دادن",
            "refund",
            "return",
            "گارانتی",
        },
        "base": 0.65,
    },
    "delivery": {
        "keywords": {
            "ارسال",
            "تحویل",
            "پست",
            "تیپاکس",
            "پیک",
            "چند روزه",
            "زمان ارسال",
            "هزینه ارسال",
            "delivery",
            "shipping",
        },
        "base": 0.6,
    },
    "payment": {
        "keywords": {
            "پرداخت",
            "درگاه",
            "پرداخت آنلاین",
            "زرین پال",
            "زرین‌پال",
            "کارت",
            "کارت به کارت",
            "تراکنش",
            "payment",
            "پرداخت امن",
        },
        "base": 0.55,
    },
    "comparison": {
        "keywords": {"مقایسه", "فرق", "تفاوت", "کدوم بهتر", "بهتره", "بهتر است"},
        "base": 0.6,
    },
    "price_availability": {
        "keywords": {
            "قیمت",
            "قیمتش",
            "قیمتشو",
            "چنده",
            "چقدره",
            "موجود",
            "موجودی",
            "ناموجود",
            "تموم",
            "دارین",
            "دارید",
        },
        "base": 0.55,
    },
    "product_detail": {
        "keywords": {"سایز", "اندازه", "شماره", "رنگ", "جنس", "مدل", "color", "size"},
        "base": 0.45,
    },
    "bulk_request": {
        "keywords": {"عمده", "پخش", "تیراژ", "تعداد بالا", "تعداد زیاد", "قیمت عمده", "bulk"},
        "base": 0.5,
    },
    "recommendation": {
        "keywords": {
            "پیشنهاد",
            "پیشنهاد بده",
            "چی پیشنهاد",
            "چی خوبه",
            "چی دارین",
            "چی دارید",
            "چه مدل",
            "چی مناسبه",
        },
        "base": 0.5,
    },
    "store_info": {
        "keywords": {
            "آدرس",
            "ساعت کاری",
            "ساعت کار",
            "شماره تماس",
            "تلفن",
            "لوکیشن",
            "نقشه",
            "راه ارتباطی",
            "اینستاگرام",
            "واتساپ",
            "تلگرام",
        },
        "base": 0.5,
    },
    "thanks": {
        "keywords": {"ممنون", "مرسی", "سپاس", "تشکر", "thanks", "thank you"},
        "base": 0.4,
    },
    "goodbye": {
        "keywords": {"خداحافظ", "فعلا", "فعلاً", "بدرود", "bye", "goodbye"},
        "base": 0.4,
    },
    "decline": {
        "keywords": {"نمیخوام", "نمی‌خوام", "چیزی نمیخوام", "بیخیال", "ولش کن"},
        "base": 0.4,
    },
}

PATTERN_PRIORITY = [
    "order_cancel",
    "order_followup",
    "purchase_intent",
    "complaint",
    "return_exchange",
    "delivery",
    "payment",
    "comparison",
    "price_availability",
    "recommendation",
    "product_request",
    "product_detail",
    "bulk_request",
    "store_info",
    "thanks",
    "goodbye",
    "decline",
]


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    value = text.translate(_ARABIC_FIX).lower()
    return " ".join(value.split())


def _score_keywords(text: str, keywords: set[str], base: float) -> tuple[float, list[str]]:
    matched = [keyword for keyword in keywords if keyword in text]
    if not matched:
        return 0.0, []
    score = min(1.0, base + 0.1 * len(matched))
    return score, matched


def detect_behavior(text: str | None) -> BehaviorMatch | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    candidates: list[tuple[float, str, list[str], list[str]]] = []
    for pattern, rule in PATTERN_RULES.items():
        score, matched = _score_keywords(normalized, rule["keywords"], rule["base"])
        if score > 0:
            candidates.append((score, pattern, matched, []))

    tags = infer_tags(normalized)
    brands = match_brands(normalized)
    tag_hits = list(tags.categories + tags.genders + tags.styles + tags.materials + tags.colors + tags.sizes)
    if tag_hits or brands:
        score = min(1.0, 0.45 + 0.08 * len(tag_hits) + 0.1 * len(brands))
        candidates.append((score, "product_request", list(brands), tag_hits))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score = candidates[0][0]
    top = [item for item in candidates if abs(item[0] - best_score) < 1e-6]
    if len(top) > 1:
        top.sort(key=lambda item: PATTERN_PRIORITY.index(item[1]) if item[1] in PATTERN_PRIORITY else 99)
    score, pattern, matched, tag_hits = top[0]
    if score < settings.BEHAVIOR_MIN_CONFIDENCE:
        return None
    reason_parts = matched + [f"tag:{tag}" for tag in tag_hits]
    reason = ", ".join(reason_parts[:10]) if reason_parts else "keyword_match"
    return BehaviorMatch(
        pattern=pattern,
        confidence=round(score, 2),
        reason=reason,
        keywords=tuple(matched),
        tags=tuple(tag_hits),
    )


def summarize_behaviors(texts: list[str]) -> tuple[dict[str, int], list[BehaviorMatch]]:
    counts: Counter[str] = Counter()
    recent: list[BehaviorMatch] = []
    for text in texts:
        match = detect_behavior(text)
        if not match:
            continue
        counts[match.pattern] += 1
        recent.append(match)
    if recent:
        recent = recent[-settings.BEHAVIOR_RECENT_LIMIT :]
    return dict(counts), recent


def build_behavior_context(behavior: dict | None) -> str | None:
    if not isinstance(behavior, dict):
        return None
    last_pattern = behavior.get("last_pattern")
    confidence = behavior.get("confidence")
    updated_at = behavior.get("updated_at")
    last_reason = behavior.get("last_reason")
    last_message = behavior.get("last_message")
    summary = behavior.get("summary") or {}
    recent = behavior.get("recent") or []
    lines = ["[BEHAVIOR]"]
    if last_pattern:
        lines.append(f"آخرین الگو: {last_pattern} (confidence={confidence})")
    if updated_at:
        lines.append(f"آخرین بروزرسانی: {updated_at}")
    if last_reason:
        lines.append(f"دلیل: {last_reason}")
    if last_message:
        lines.append(f"آخرین پیام: {last_message}")
    if summary:
        top = sorted(summary.items(), key=lambda item: item[1], reverse=True)[:5]
        lines.append("خلاصه رفتار: " + "، ".join(f"{k}({v})" for k, v in top))
    if recent:
        lines.append("نمونه‌های اخیر:")
        for item in recent:
            if isinstance(item, dict):
                lines.append(f"- {item.get('pattern')} ({item.get('confidence')})")
            elif isinstance(item, BehaviorMatch):
                lines.append(f"- {item.pattern} ({item.confidence})")
    return "\n".join(lines).strip()


async def get_user_messages(
    session: AsyncSession,
    user_id: int,
    limit: int,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .where(Message.role == "user")
        .where(Message.type != "read")
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def analyze_user_behavior(
    session: AsyncSession,
    user_id: int,
    current_text: str | None,
    limit: int,
) -> tuple[BehaviorMatch | None, dict[str, int], list[dict[str, Any]]]:
    messages = await get_user_messages(session, user_id, limit)
    texts = [msg.content_text for msg in messages if msg.content_text]
    if current_text and (not texts or texts[-1] != current_text):
        texts.append(current_text)
    summary_counts, recent_matches = summarize_behaviors(texts)
    recent_payload: list[dict[str, Any]] = []
    for match in recent_matches:
        recent_payload.append(
            {
                "pattern": match.pattern,
                "confidence": match.confidence,
                "reason": match.reason,
            }
        )
    match = detect_behavior(current_text)
    return match, summary_counts, recent_payload


def build_behavior_profile(
    match: BehaviorMatch | None,
    summary_counts: dict[str, int],
    recent_payload: list[dict[str, Any]],
    last_message: str | None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(previous or {})
    payload["summary"] = summary_counts
    payload["recent"] = recent_payload
    payload["updated_at"] = utc_now().isoformat()
    payload["last_message"] = (last_message or "")[:500]
    if match:
        payload.update(
            {
                "last_pattern": match.pattern,
                "confidence": match.confidence,
                "last_reason": match.reason,
            }
        )
    return payload
