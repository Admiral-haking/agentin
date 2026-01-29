from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.services.conversation_state import infer_category as infer_state_category
from app.services.guardrails import (
    is_angry,
    is_decline,
    is_goodbye,
    is_greeting,
    is_purchase_confirmation,
    is_thanks,
    needs_product_details,
    wants_address,
    wants_contact,
    wants_hours,
    wants_phone,
    wants_product_intent,
    wants_product_address,
    wants_product_link,
    wants_trust,
    wants_website,
)

_INTENT_STORE_INFO = "store_info"
_INTENT_PRODUCT_DISCOVERY = "product_discovery"
_INTENT_PRODUCT_SPECIFIC = "product_specific"
_INTENT_PRODUCT_LINK = "product_link_request"
_INTENT_PRICE = "price_availability"
_INTENT_ORDER = "order_intent"
_INTENT_COMPLAINT = "complaint_support"
_INTENT_CAMPAIGN = "campaign_discount"
_INTENT_AMBIGUOUS_STORE_PRODUCTS = "ambiguous_store_vs_products"
_INTENT_SMALLTALK = "smalltalk"
_INTENT_UNKNOWN = "unknown"

_SUPPORT_KEYWORDS = {
    "شکایت",
    "ناراضی",
    "مشکل",
    "پرداخت",
    "ارسال",
    "تاخیر",
    "تاخیر",
    "خراب",
    "نرسید",
    "مرجوع",
    "تعویض",
    "refund",
    "refunds",
    "complaint",
    "support",
}

_CAMPAIGN_KEYWORDS = {
    "تخفیف",
    "کد تخفیف",
    "کد هدیه",
    "کمپین",
    "حراج",
    "پیشنهاد ویژه",
    "discount",
}

_PRODUCT_SPECIFIC_HINTS = {
    "مدل",
    "کد",
    "sku",
    "code",
}


@dataclass(frozen=True)
class RouterDecision:
    intent: str
    category: str
    confidence: float
    evidence_keywords: tuple[str, ...]
    risk_level: str


def _collect_hits(text: str, keywords: Iterable[str]) -> list[str]:
    lowered = (text or "").lower()
    return [kw for kw in keywords if kw in lowered]


def route_intent(text: str | None) -> RouterDecision:
    message = (text or "").strip()
    lowered = message.lower()
    evidence: list[str] = []

    if wants_product_address(message):
        evidence.extend(_collect_hits(lowered, ["آدرس", "محصول", "محصولات", "کالا"]))
        return RouterDecision(
            intent=_INTENT_AMBIGUOUS_STORE_PRODUCTS,
            category="unknown",
            confidence=0.92,
            evidence_keywords=tuple(evidence),
            risk_level="HIGH",
        )

    if wants_product_link(message):
        evidence.extend(_collect_hits(lowered, ["لینک", "پرداخت", "صفحه"]))
        return RouterDecision(
            intent=_INTENT_PRODUCT_LINK,
            category=_infer_category(message),
            confidence=0.95,
            evidence_keywords=tuple(evidence),
            risk_level="HIGH",
        )

    if wants_address(message) or wants_hours(message) or wants_phone(message) or wants_contact(message) or wants_website(message) or wants_trust(message):
        evidence.extend(_collect_hits(lowered, ["آدرس", "ساعت", "تلفن", "شماره", "شعبه", "سایت", "اینماد"]))
        return RouterDecision(
            intent=_INTENT_STORE_INFO,
            category="unknown",
            confidence=0.9,
            evidence_keywords=tuple(evidence),
            risk_level="HIGH",
        )

    if is_angry(message) or _collect_hits(lowered, _SUPPORT_KEYWORDS):
        evidence.extend(_collect_hits(lowered, _SUPPORT_KEYWORDS))
        return RouterDecision(
            intent=_INTENT_COMPLAINT,
            category=_infer_category(message),
            confidence=0.85,
            evidence_keywords=tuple(evidence),
            risk_level="HIGH",
        )

    if is_purchase_confirmation(message):
        evidence.extend(_collect_hits(lowered, ["ثبت", "میخوام", "بخر", "سفارش"]))
        return RouterDecision(
            intent=_INTENT_ORDER,
            category=_infer_category(message),
            confidence=0.8,
            evidence_keywords=tuple(evidence),
            risk_level="HIGH",
        )

    if _collect_hits(lowered, _CAMPAIGN_KEYWORDS):
        evidence.extend(_collect_hits(lowered, _CAMPAIGN_KEYWORDS))
        return RouterDecision(
            intent=_INTENT_CAMPAIGN,
            category=_infer_category(message),
            confidence=0.7,
            evidence_keywords=tuple(evidence),
            risk_level="MED",
        )

    if is_greeting(message) or is_thanks(message) or is_goodbye(message) or is_decline(message):
        return RouterDecision(
            intent=_INTENT_SMALLTALK,
            category="unknown",
            confidence=0.6,
            evidence_keywords=tuple(_collect_hits(lowered, ["سلام", "مرسی", "ممنون", "خداحافظ"])),
            risk_level="LOW",
        )

    if needs_product_details(message):
        evidence.extend(_collect_hits(lowered, ["قیمت", "موجود", "سایز", "رنگ"]))
        return RouterDecision(
            intent=_INTENT_PRICE,
            category=_infer_category(message),
            confidence=0.6,
            evidence_keywords=tuple(evidence),
            risk_level="MED",
        )

    if wants_product_intent(message):
        evidence.extend(_collect_hits(lowered, ["محصول", "لیست", "مدل", "کفش", "عطر", "لباس"]))
        intent = _INTENT_PRODUCT_DISCOVERY
        if any(hint in lowered for hint in _PRODUCT_SPECIFIC_HINTS):
            intent = _INTENT_PRODUCT_SPECIFIC
        if "ghlbedovom.com/product" in lowered:
            intent = _INTENT_PRODUCT_SPECIFIC
        return RouterDecision(
            intent=intent,
            category=_infer_category(message),
            confidence=0.55,
            evidence_keywords=tuple(evidence),
            risk_level="MED",
        )

    return RouterDecision(
        intent=_INTENT_UNKNOWN,
        category=_infer_category(message),
        confidence=0.3,
        evidence_keywords=tuple(evidence),
        risk_level="LOW",
    )


def _infer_category(text: str | None) -> str:
    category = infer_state_category(text)
    return category or "unknown"
