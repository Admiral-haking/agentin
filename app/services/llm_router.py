from __future__ import annotations

from app.core.config import settings
from app.schemas.webhook import NormalizedMessage

SENSITIVE_KEYWORDS = {
    "payment",
    "refund",
    "charge",
    "complaint",
    "legal",
    "security",
    "privacy",
    "account",
    "ban",
    "hack",
    "access",
    "پرداخت",
    "بازگشت وجه",
    "شکایت",
    "قانونی",
    "امنیت",
    "حریم خصوصی",
    "اکانت",
    "بن",
    "هک",
    "دسترسی",
}


def choose_provider(
    message: NormalizedMessage,
    ai_mode: str | None,
) -> str:
    if ai_mode in {"openai", "deepseek"}:
        return ai_mode

    if settings.LLM_MODE in {"openai", "deepseek"}:
        return settings.LLM_MODE

    text = (message.text or "").lower()
    if len(text) > 200 or text.count("?") > 1:
        return "openai"
    if any(keyword in text for keyword in SENSITIVE_KEYWORDS):
        return "openai"
    return "deepseek"
