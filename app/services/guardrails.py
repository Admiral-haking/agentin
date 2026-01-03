from __future__ import annotations

import json
import re
from typing import Iterable

from pydantic import ValidationError

from app.core.config import settings
from app.knowledge.store import (
    get_branches_text,
    get_hours_text,
    get_phone_text,
    get_trust_text,
    get_website_url,
)
from app.schemas.send import Button, OutboundPlan, QuickReplyOption

FALLBACK_GENERAL = "سلام! برای راهنمایی دقیق‌تر، بگید دنبال چه محصول/دسته‌ای هستید یا بودجه‌تون چقدره؟"
FALLBACK_MEDIA = "پیام رسانه‌ای دریافت شد. لطفاً توضیح کوتاه متنی بفرستید تا سریع‌تر راهنمایی کنیم."
FALLBACK_AUDIO = "پیام صوتی دریافت شد. لطفاً متن کوتاه ارسال کنید تا سریع‌تر کمک کنیم."
FALLBACK_LLM = (
    "خوشحال می‌شم راهنمایی کنم؛ لطفاً اسم/مدل محصول یا یه عکس بفرستید تا دقیق‌تر کمک کنم."
)
GENERIC_FALLBACKS = {
    "لطفاً کمی دقیق‌تر بگید تا بهتر راهنمایی کنم 🙏",
    "لطفاً کمی دقیق‌تر بگید تا بهتر راهنمایی کنم",
    "لطفاً کمی دقیق‌تر بفرمایید.",
}
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
LIST_PREFIX_RE = re.compile(r"^\s*([-*•]|\d+[.)])\s+", re.MULTILINE)
MULTISPACE_RE = re.compile(r"[ \t]{2,}")
PUNCT_SPACE_RE = re.compile(r"\s+([،؛:!؟.,])")

GREETING_KEYWORDS = {
    "سلام",
    "درود",
    "وقت بخیر",
    "وقت‌ بخیر",
    "hi",
    "hello",
}
ADDRESS_KEYWORDS = {
    "آدرس",
    "شعبه",
    "لوکیشن",
    "مکان",
    "کجا هستین",
    "کجاست",
    "نشان",
    "نقشه",
}
HOURS_KEYWORDS = {
    "ساعت کاری",
    "ساعت کار",
    "ساعت چند",
    "چه ساعتی",
    "باز هستین",
    "باز هستید",
    "تایم",
}
PHONE_KEYWORDS = {
    "تلفن",
    "تماس",
    "شماره تماس",
    "پشتیبانی تلفنی",
}
WEBSITE_KEYWORDS = {
    "سایت",
    "وبسایت",
    "وب‌سایت",
    "لینک سایت",
}
TRUST_KEYWORDS = {
    "اعتماد",
    "اینماد",
    "نماد اعتماد",
    "امن",
    "زرین‌پال",
    "زرین پال",
    "قابل اعتماد",
}
PRICE_KEYWORDS = {
    "قیمت",
    "چنده",
    "هزینه",
    "موجود",
    "موجودی",
    "دارین",
    "سایز",
    "رنگ",
    "مدل",
}
PRODUCT_INTENT_KEYWORDS = {
    "محصول",
    "محصولات",
    "کاتالوگ",
    "لیست",
    "کالا",
    "چی دارید",
    "چی داری",
    "پیشنهاد",
    "چی پیشنهاد",
    "چه چیزی",
    "میخوام",
    "میخواهم",
    "می‌خوام",
    "می‌خواهم",
    "میگردم",
    "می‌گردم",
    "دنبال",
    "دارید",
    "دارین",
    "دسته",
    "دسته بندی",
    "دسته‌بندی",
    "منو",
    "کالکشن",
    "price",
    "product",
    "products",
    "catalog",
    "list",
    "category",
    "collection",
}
ANGRY_KEYWORDS = {
    "ناراضی",
    "عصبانی",
    "بد",
    "افتضاح",
    "شکایت",
    "کلاهبرداری",
    "پولم",
    "مشکل دارم",
    "نمیاد",
    "نیومد",
}

QUICK_REPLY_MENU = ["خرید", "ثبت سفارش", "مشاهده محصولات", "پشتیبانی", "آدرس شعب"]


def fallback_for_message_type(message_type: str) -> str:
    if message_type == "audio":
        return FALLBACK_AUDIO
    if message_type in {"image", "video", "media"}:
        return FALLBACK_MEDIA
    return FALLBACK_GENERAL


def post_process(text: str | None, max_chars: int | None = None, fallback_text: str | None = None) -> str:
    if not text:
        return fallback_text or FALLBACK_GENERAL
    cleaned = text.strip()
    if parse_structured_response(cleaned):
        return cleaned
    cleaned = _sanitize_text(cleaned)
    if not cleaned or cleaned in GENERIC_FALLBACKS:
        return fallback_text or FALLBACK_GENERAL
    limit = max_chars or settings.MAX_RESPONSE_CHARS
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip()
        cleaned = f"{cleaned}..."
    return cleaned


def fallback_llm_text(override: str | None = None) -> str:
    if override:
        return override
    return FALLBACK_LLM


def parse_structured_response(text: str) -> OutboundPlan | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    try:
        return OutboundPlan.model_validate(payload)
    except ValidationError:
        return None


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def _sanitize_text(text: str) -> str:
    cleaned = MARKDOWN_LINK_RE.sub(r"\1: \2", text)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = LIST_PREFIX_RE.sub("", cleaned)
    cleaned = PUNCT_SPACE_RE.sub(r"\1", cleaned)
    cleaned = MULTISPACE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def is_greeting(text: str) -> bool:
    return _contains_any(text, GREETING_KEYWORDS)


def needs_product_details(text: str) -> bool:
    return _contains_any(text, PRICE_KEYWORDS)


def wants_product_intent(text: str) -> bool:
    if _contains_any(text, PRICE_KEYWORDS):
        return True
    return _contains_any(text, PRODUCT_INTENT_KEYWORDS)


def is_angry(text: str) -> bool:
    return _contains_any(text, ANGRY_KEYWORDS)


def wants_website(text: str) -> bool:
    return _contains_any(text, WEBSITE_KEYWORDS)


def wants_address(text: str) -> bool:
    return _contains_any(text, ADDRESS_KEYWORDS)


def wants_hours(text: str) -> bool:
    return _contains_any(text, HOURS_KEYWORDS)


def wants_phone(text: str) -> bool:
    return _contains_any(text, PHONE_KEYWORDS)


def wants_trust(text: str) -> bool:
    return _contains_any(text, TRUST_KEYWORDS)


def build_quick_reply_plan() -> OutboundPlan:
    options = [
        QuickReplyOption(title=title, payload=title) for title in QUICK_REPLY_MENU
    ]
    return OutboundPlan(
        type="quick_reply",
        text="سلام! چطور می‌تونم کمکتون کنم؟",
        quick_replies=options,
    )


def build_address_response() -> str:
    branches_text = get_branches_text()
    return (
        f"آدرس شعب فروشگاه قلب دوم:\\n{branches_text}\\n"
        "کدوم محدوده مشهد هستید تا نزدیک‌ترین شعبه رو معرفی کنم؟"
    )


def build_hours_response() -> str:
    return f"{get_hours_text()}\nاگر قصد مراجعه دارید، کدوم محدوده مشهد هستید؟"


def build_phone_response() -> str:
    return f"{get_phone_text()}\nبرای خرید آنلاین هم می‌تونید از وب‌سایت استفاده کنید."


def build_website_plan() -> OutboundPlan:
    url = get_website_url()
    return OutboundPlan(
        type="button",
        text="وب‌سایت رسمی فروشگاه قلب دوم:",
        buttons=[Button(type="web_url", title="مشاهده سایت", url=url)],
    )


def build_trust_response() -> str:
    return get_trust_text()


def build_product_details_question() -> str:
    return (
        "برای اعلام قیمت/موجودی، لطفاً عکس محصول یا نام دقیق + مدل + سایز/رنگ رو بفرستید 😊"
    )


def build_angry_response() -> str:
    return (
        "متأسفم بابت مشکلی که پیش اومده 🙏 لطفاً شماره سفارش و یک اسکرین‌شات ارسال کنید تا سریع پیگیری کنیم."
    )


def build_rule_based_plan(
    message_type: str,
    text: str | None,
    is_first_message: bool,
) -> OutboundPlan | None:
    normalized = _normalize_text(text)

    if not text and message_type in {"audio", "image", "video", "media"}:
        return OutboundPlan(type="text", text=fallback_for_message_type(message_type))

    if not normalized:
        if is_first_message:
            return build_quick_reply_plan()
        return OutboundPlan(type="text", text=fallback_for_message_type("text"))

    if is_first_message and is_greeting(normalized):
        return build_quick_reply_plan()

    if wants_trust(normalized):
        return OutboundPlan(type="text", text=build_trust_response())

    if wants_website(normalized):
        return build_website_plan()

    if wants_address(normalized):
        return OutboundPlan(type="text", text=build_address_response())

    if wants_hours(normalized):
        return OutboundPlan(type="text", text=build_hours_response())

    if wants_phone(normalized):
        return OutboundPlan(type="text", text=build_phone_response())

    if is_angry(normalized):
        return OutboundPlan(type="text", text=build_angry_response())

    if needs_product_details(normalized):
        return OutboundPlan(type="text", text=build_product_details_question())

    return None


def _extract_numbered_options(lines: Iterable[str]) -> list[str]:
    options: list[str] = []
    for line in lines:
        match = re.match(r"^\s*\d+[\).:-]\s*(.+)$", line)
        if match:
            options.append(match.group(1).strip())
    return options


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip()


def plan_outbound(text: str) -> OutboundPlan:
    structured = parse_structured_response(text)
    if structured:
        return structured

    link_match = re.search(r"https?://\S+", text)
    if link_match:
        url = link_match.group(0).rstrip(").,")
        button = Button(type="web_url", title="مشاهده لینک", url=url)
        return OutboundPlan(type="button", text=text, buttons=[button])

    if "ghlbedovom.com" in text:
        url = get_website_url()
        button = Button(type="web_url", title="مشاهده سایت", url=url)
        return OutboundPlan(type="button", text=text, buttons=[button])

    options = _extract_numbered_options(text.splitlines())
    if 1 < len(options) <= settings.MAX_QUICK_REPLIES:
        quick_replies = [
            QuickReplyOption(
                title=_truncate(option, settings.QUICK_REPLY_TITLE_MAX_CHARS),
                payload=_truncate(option, settings.QUICK_REPLY_PAYLOAD_MAX_CHARS),
            )
            for option in options
        ]
        return OutboundPlan(type="quick_reply", text=text, quick_replies=quick_replies)

    return OutboundPlan(type="text", text=text)
