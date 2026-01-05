from __future__ import annotations

import json
import re
from typing import Iterable
from urllib.parse import urlparse

from pydantic import ValidationError

from app.core.config import settings
from app.knowledge.store import (
    get_branch_cards,
    get_branches_text,
    get_contact_links,
    get_contact_text,
    get_hours_text,
    get_phone_text,
    get_trust_text,
    get_website_url,
)
from app.schemas.send import Button, OutboundPlan, QuickReplyOption, TemplateElement

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
PERSIAN_LETTER_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF]")
URL_RE = re.compile(r"(https?://\S+|ghlbedovom\.com\S*)")

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
    "شعبات",
    "لوکیشن",
    "مکان",
    "کجا هستین",
    "کجاست",
    "نشان",
    "نقشه",
    "نشانی",
}
HOURS_KEYWORDS = {
    "ساعت کاری",
    "ساعت کار",
    "ساعت چند",
    "چه ساعتی",
    "زمان حضور",
    "ساعت حضور",
    "چه زمانی حضور",
    "حضور دارین",
    "حضور دارید",
    "تا چه ساعتی",
    "باز هستین",
    "باز هستید",
    "تایم",
    "ساعت باز",
    "ساعت بسته",
}
PHONE_KEYWORDS = {
    "تلفن",
    "تماس",
    "شماره تماس",
    "شماره تماس ها",
    "شماره تماس‌ها",
    "پشتیبانی تلفنی",
}
CONTACT_KEYWORDS = {
    "راه ارتباطی",
    "راه های ارتباطی",
    "راه‌های ارتباطی",
    "راه تماس",
    "شماره پشتیبانی",
    "شماره ها",
    "شماره‌ها",
    "ارتباط با",
    "پشتیبانی",
    "راه ارتباط",
    "پیج",
    "اینستاگرام",
    "واتساپ",
    "تلگرام",
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
    "بودجه",
    "ارزان",
    "گرون",
}
PRODUCT_INTENT_KEYWORDS = {
    "محصول",
    "محصولات",
    "کاتالوگ",
    "لیست",
    "کالا",
    "ویترین",
    "گالری",
    "نمونه",
    "چی دارید",
    "چی داری",
    "پیشنهاد",
    "چی پیشنهاد",
    "دسته",
    "دسته بندی",
    "دسته‌بندی",
    "منو",
    "کالکشن",
    "مدل ها",
    "مدل‌ها",
    "کفش",
    "صندل",
    "دمپایی",
    "عطر",
    "ادکلن",
    "کیف",
    "لباس",
    "پوشاک",
    "اکسسوری",
    "آرایشی",
    "بهداشتی",
    "جوراب",
    "شال",
    "price",
    "product",
    "products",
    "catalog",
    "list",
    "category",
    "collection",
}
CONTINUE_KEYWORDS = {
    "ادامه",
    "بیشتر",
    "بعدی",
    "صفحه بعد",
    "موارد بیشتر",
    "نمایش بیشتر",
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
THANKS_KEYWORDS = {
    "ممنون",
    "مرسی",
    "سپاس",
    "تشکر",
    "thx",
    "thanks",
    "thank you",
}
GOODBYE_KEYWORDS = {
    "خداحافظ",
    "فعلا",
    "فعلاً",
    "بدرود",
    "روز بخیر",
    "شب بخیر",
    "bye",
    "goodbye",
    "see you",
}
DECLINE_KEYWORDS = {
    "نمیخوام",
    "نمی‌خوام",
    "نمیخواهم",
    "چیزی نمیخوام",
    "فعلا نمیخوام",
    "نه",
    "خیر",
    "بیخیال",
}
PURCHASE_CONFIRM_KEYWORDS = {
    "همینو میخوام",
    "همین رو میخوام",
    "همین میخوام",
    "اینو میخوام",
    "این رو میخوام",
    "این میخوام",
    "میخوامش",
    "میخوام بخرم",
    "میخرم",
    "می خرم",
    "میخرمش",
    "میخواهم",
    "می‌خواهم",
    "می‌خوام",
    "ثبت کن",
    "ثبت سفارش",
    "سفارش بده",
    "میخرم الان",
}
REPEAT_KEYWORDS = {
    "دوباره",
    "مجدد",
    "یه بار دیگه",
    "یک بار دیگه",
    "تکرار",
    "باز بفرست",
    "باز بگو",
}
LINK_KEYWORDS = {
    "لینک محصول",
    "لینک خرید",
    "لینک پرداخت",
    "لینک مستقیم",
    "لینکش",
    "لینک",
    "آدرس محصول",
}
GENERIC_SLOT_KEYWORDS = {
    "جنسیت",
    "سایز",
    "سبک",
    "بازه قیمت",
    "بودجه",
    "رسمی",
    "اسپرت",
}
PRODUCT_PROMPT_KEYWORDS = {
    "مدل",
    "سایز",
    "رنگ",
    "قیمت",
    "موجودی",
    "سبک",
    "بازه قیمت",
    "بودجه",
}
PRICE_WORDS = {"تومان", "تومن", "ریال", "هزار", "میلیون"}
OPTION_PATTERN = re.compile(r"شماره\s*[0-9]{1,2}")
BUDGET_PHRASE_RE = re.compile(r"\d[\d,]*\s*(هزار|میلیون)?\s*(تومان|تومن|ریال)")

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
    if _is_mostly_latin(cleaned):
        return fallback_text or FALLBACK_GENERAL
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


def _plan_to_text(plan: OutboundPlan) -> str:
    if plan.text:
        return plan.text
    if plan.type == "generic_template":
        lines: list[str] = []
        for element in plan.elements:
            line = element.title
            if element.subtitle:
                line = f"{line} - {element.subtitle}"
            lines.append(line)
        return "\n".join(lines)
    return ""


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


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    value = text.translate(_ARABIC_FIX).lower()
    return " ".join(value.split())


def _sanitize_text(text: str) -> str:
    cleaned = MARKDOWN_LINK_RE.sub(r"\1: \2", text)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = LIST_PREFIX_RE.sub("", cleaned)
    cleaned = PUNCT_SPACE_RE.sub(r"\1", cleaned)
    cleaned = MULTISPACE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _is_mostly_latin(text: str) -> bool:
    if not text:
        return False
    latin_count = len(LATIN_LETTER_RE.findall(text))
    persian_count = len(PERSIAN_LETTER_RE.findall(text))
    if latin_count < 10:
        return False
    return persian_count < max(3, latin_count // 4)


def _extract_urls(text: str) -> list[str]:
    if not text:
        return []
    urls: list[str] = []
    for match in URL_RE.findall(text):
        url = match.strip().rstrip(").,")
        if not url:
            continue
        if not url.startswith("http"):
            url = f"https://{url.lstrip('/')}"
        urls.append(url)
    return urls


def _is_root_link(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc not in {"ghlbedovom.com", "www.ghlbedovom.com"}:
        return False
    return parsed.path in {"", "/"}


def _should_force_persian(reply_text: str, user_text: str | None) -> bool:
    if not reply_text:
        return False
    if PERSIAN_LETTER_RE.search(reply_text):
        return False
    if not LATIN_LETTER_RE.search(reply_text):
        return False
    return bool(PERSIAN_LETTER_RE.search(user_text or ""))


def _contains_any(text: str, keywords: set[str]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(keyword) in normalized for keyword in keywords)


def is_greeting(text: str) -> bool:
    return _contains_any(text, GREETING_KEYWORDS)


def needs_product_details(text: str) -> bool:
    if _contains_any(text, CONTACT_KEYWORDS | WEBSITE_KEYWORDS | ADDRESS_KEYWORDS | HOURS_KEYWORDS | PHONE_KEYWORDS | TRUST_KEYWORDS):
        return False
    return _contains_any(text, PRICE_KEYWORDS)


def wants_product_intent(text: str) -> bool:
    if _contains_any(text, CONTACT_KEYWORDS | WEBSITE_KEYWORDS | ADDRESS_KEYWORDS | HOURS_KEYWORDS | PHONE_KEYWORDS | TRUST_KEYWORDS):
        return False
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


def wants_contact(text: str) -> bool:
    return _contains_any(text, CONTACT_KEYWORDS)


def wants_more_products(text: str) -> bool:
    if _contains_any(
        text,
        CONTACT_KEYWORDS
        | WEBSITE_KEYWORDS
        | ADDRESS_KEYWORDS
        | HOURS_KEYWORDS
        | PHONE_KEYWORDS
        | TRUST_KEYWORDS,
    ):
        return False
    return _contains_any(text, CONTINUE_KEYWORDS)


def wants_repeat(text: str) -> bool:
    return _contains_any(text, REPEAT_KEYWORDS)


def wants_product_link(text: str) -> bool:
    if not text:
        return False
    if wants_website(text):
        return False
    normalized = _normalize_text(text)
    return any(keyword in normalized for keyword in LINK_KEYWORDS)


def is_purchase_confirmation(text: str | None) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in PURCHASE_CONFIRM_KEYWORDS)


def wants_trust(text: str) -> bool:
    return _contains_any(text, TRUST_KEYWORDS)


def is_thanks(text: str) -> bool:
    return _contains_any(text, THANKS_KEYWORDS)


def is_goodbye(text: str) -> bool:
    return _contains_any(text, GOODBYE_KEYWORDS)


def is_decline(text: str) -> bool:
    return _contains_any(text, DECLINE_KEYWORDS)


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
    return f"آدرس شعب فروشگاه قلب دوم:\\n{branches_text}"


def build_hours_response() -> str:
    return get_hours_text()


def build_phone_response() -> str:
    return get_phone_text()


def build_website_plan() -> OutboundPlan:
    url = get_website_url()
    return OutboundPlan(
        type="button",
        text="وب‌سایت رسمی فروشگاه قلب دوم:",
        buttons=[Button(type="web_url", title="مشاهده سایت", url=url)],
    )


def build_trust_response() -> str:
    return get_trust_text()


def build_contact_response() -> str:
    return get_contact_text(include_website=False)


def build_contact_plan() -> OutboundPlan:
    links = get_contact_links(include_website=False)
    elements: list[TemplateElement] = []
    for item in links:
        title = item.get("title") or "ارتباط"
        url = item.get("url")
        if not url:
            continue
        elements.append(
            TemplateElement(
                title=title,
                subtitle="برای ارتباط روی دکمه بزنید.",
                buttons=[Button(type="web_url", title="مشاهده", url=url)],
            )
        )
    if elements:
        return OutboundPlan(type="generic_template", elements=elements)
    return OutboundPlan(type="text", text=build_contact_response())


def build_branches_plan() -> OutboundPlan:
    cards = get_branch_cards()
    elements: list[TemplateElement] = []
    for item in cards:
        title = item.get("title") or "شعبه"
        subtitle = item.get("subtitle") or None
        url = item.get("url")
        buttons = []
        if url:
            buttons.append(Button(type="web_url", title="نقشه", url=url))
        elements.append(
            TemplateElement(
                title=title,
                subtitle=subtitle,
                buttons=buttons[: settings.MAX_BUTTONS],
            )
        )
    if elements:
        return OutboundPlan(type="generic_template", elements=elements)
    return OutboundPlan(type="text", text=build_address_response())


def build_product_details_question() -> str:
    return (
        "برای اعلام قیمت/موجودی، لطفاً عکس محصول یا نام دقیق + مدل + سایز/رنگ رو بفرستید 😊"
    )


def build_angry_response() -> str:
    return (
        "متأسفم بابت مشکلی که پیش اومده 🙏 لطفاً شماره سفارش و یک اسکرین‌شات ارسال کنید تا سریع پیگیری کنیم."
    )


def build_thanks_response() -> str:
    return "خواهش می‌کنم! اگر سوالی داشتید در خدمتم."


def build_decline_response() -> str:
    return "باشه، هر وقت سوالی داشتید خوشحال می‌شم کمک کنم."


def build_goodbye_response() -> str:
    return "روز خوبی داشته باشید! هر وقت سوالی بود پیام بدید."


def build_rule_based_plan(
    message_type: str,
    text: str | None,
    is_first_message: bool,
) -> OutboundPlan | None:
    normalized = _normalize_text(text)
    token_count = len(normalized.split()) if normalized else 0

    if not text and message_type in {"audio", "image", "video", "media"}:
        return OutboundPlan(type="text", text=fallback_for_message_type(message_type))

    if not normalized:
        if is_first_message:
            return build_quick_reply_plan()
        return OutboundPlan(type="text", text=fallback_for_message_type("text"))

    if is_first_message and is_greeting(normalized):
        return build_quick_reply_plan()

    if is_greeting(normalized) and token_count <= 2:
        return OutboundPlan(type="text", text="سلام! چطور می‌تونم کمکتون کنم؟")

    if is_thanks(normalized) and token_count <= 4:
        return OutboundPlan(type="text", text=build_thanks_response())

    if is_decline(normalized) and token_count <= 5:
        return OutboundPlan(type="text", text=build_decline_response())

    if is_goodbye(normalized) and token_count <= 4:
        return OutboundPlan(type="text", text=build_goodbye_response())

    if wants_trust(normalized):
        return OutboundPlan(type="text", text=build_trust_response())

    if wants_contact(normalized) or wants_phone(normalized):
        return build_contact_plan()

    if wants_website(normalized):
        return build_website_plan()

    if wants_address(normalized):
        return build_branches_plan()

    if wants_hours(normalized):
        return OutboundPlan(type="text", text=build_hours_response())

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

    link_match = re.search(r"(https?://\S+|ghlbedovom\.com/\S+)", text)
    if link_match:
        url = link_match.group(0).rstrip(").,")
        if not url.startswith("http"):
            url = f"https://{url.lstrip('/')}"
        button = Button(type="web_url", title="مشاهده لینک", url=url)
        return OutboundPlan(type="button", text=text, buttons=[button])

    if "ghlbedovom.com" in text:
        url_match = re.search(r"ghlbedovom\.com\S*", text)
        url = url_match.group(0) if url_match else get_website_url()
        if not url.startswith("http"):
            url = f"https://{url.lstrip('/')}"
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


def _limit_sentences(text: str, max_sentences: int) -> str:
    if not text or max_sentences <= 0:
        return text
    parts = re.split(r"[.!؟?\n]+", text.strip())
    if len(parts) <= max_sentences:
        return text
    return " ".join(part.strip() for part in parts[:max_sentences] if part.strip()).strip()


def _limit_emojis(text: str, max_emojis: int) -> str:
    if not text or max_emojis < 0:
        return text
    count = 0
    output = []
    for ch in text:
        if EMOJI_RE.match(ch):
            count += 1
            if count > max_emojis:
                continue
        output.append(ch)
    return "".join(output)


def _looks_like_generic_slot_prompt(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    hits = sum(1 for keyword in GENERIC_SLOT_KEYWORDS if keyword in normalized)
    return hits >= 2


def _looks_like_product_prompt(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in PRODUCT_PROMPT_KEYWORDS)


def _extract_budget_phrase(text: str) -> str | None:
    if not text:
        return None
    match = BUDGET_PHRASE_RE.search(text)
    if not match:
        return None
    return match.group(0).strip()


def _contains_price(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if any(word in normalized for word in PRICE_WORDS):
        return True
    return bool(re.search(r"\d{3,}", normalized))


def validate_reply_or_rewrite(
    plan: OutboundPlan,
    state: dict[str, object] | None,
    user_message: str | None,
    *,
    has_products_context: bool,
    allow_generic_slots: bool,
) -> tuple[OutboundPlan, list[str]]:
    reasons: list[str] = []
    original_plan = plan
    text = plan.text or _plan_to_text(plan)
    normalized_user = _normalize_text(user_message)
    selected_product = None
    if isinstance(state, dict):
        selected_product = state.get("selected_product")

    if wants_product_link(normalized_user):
        page_url = None
        if isinstance(selected_product, dict):
            page_url = selected_product.get("page_url") or selected_product.get("url")
        if isinstance(page_url, str) and page_url.strip():
            reply = f"حتماً 🙂 لینک مستقیم محصول: {page_url.strip()}"
            return OutboundPlan(type="text", text=reply), ["link_request_handled"]
        reply = "برای ارسال لینک، لطفاً اسم دقیق مدل یا یک عکس/لینک از محصول بفرستید."
        return OutboundPlan(type="text", text=reply), ["link_request_missing"]

    if selected_product and _looks_like_generic_slot_prompt(text):
        reply = "برای ثبت سفارش، لطفاً سایز/رنگ و تعداد مدنظرتون رو بگید."
        return OutboundPlan(type="text", text=reply), ["template_blocked:selected_product"]

    intent = None
    category = None
    if isinstance(state, dict):
        intent = state.get("intent")
        category = state.get("category")

    if intent == "store_info" and _looks_like_product_prompt(text):
        reply = "بفرمایید دقیقاً کدوم اطلاعات فروشگاه مدنظرتونه؟"
        return OutboundPlan(type="text", text=reply), ["template_blocked:store_info"]

    if any(_is_root_link(url) for url in _extract_urls(text)) and not wants_website(normalized_user):
        if intent == "store_info":
            reply = "اگر لینک سایت رو لازم دارید، بفرمایید تا دقیق بفرستم."
        else:
            reply = "برای لینک دقیق محصول، لطفاً اسم/مدل یا عکس محصول رو بفرستید."
        return OutboundPlan(type="text", text=reply), ["root_link_blocked"]

    if settings.DEFAULT_LANGUAGE == "fa" and _should_force_persian(text, user_message):
        reply = fallback_llm_text()
        return OutboundPlan(type="text", text=reply), ["language_forced_fa"]

    if not allow_generic_slots and _looks_like_generic_slot_prompt(text):
        reply = "برای معرفی دقیق‌تر، لطفاً نوع/رنگ یا مدل دقیق رو بفرستید."
        return OutboundPlan(type="text", text=reply), ["template_blocked:category_slots"]

    if text and not has_products_context and not selected_product:
        if _contains_price(text):
            reply = "برای اعلام قیمت دقیق، لطفاً اسم/مدل محصول یا یک عکس بفرستید."
            return OutboundPlan(type="text", text=reply), ["hallucination_prevented:price"]
        if OPTION_PATTERN.search(text):
            reply = "برای معرفی دقیق، لطفاً اسم مدل یا عکس محصول را بفرستید."
            return OutboundPlan(type="text", text=reply), ["hallucination_prevented:options"]

    budget_phrase = _extract_budget_phrase(user_message or "")
    if budget_phrase and _contains_price(text) and budget_phrase not in text:
        reply = f"اوکی، بازه قیمت مدنظرتون {budget_phrase} هست. مدل دقیق یا عکسش رو بفرستید."
        return OutboundPlan(type="text", text=reply), ["budget_reflected"]

    if text:
        text = _limit_questions(text, 1)
        text = _limit_sentences(text, 4)
        text = _limit_emojis(text, 1)
    if original_plan.type in {"text", "button", "quick_reply"}:
        plan.text = text or plan.text or fallback_llm_text()
        return plan, reasons
    if reasons:
        return OutboundPlan(type="text", text=text or fallback_llm_text()), reasons
    return original_plan, reasons
