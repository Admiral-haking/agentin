from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.send import OutboundPlan, QuickReplyOption
from app.utils.time import utc_now

ORDER_KEYWORDS = {
    "خرید",
    "سفارش",
    "ثبت سفارش",
    "میخوام بخرم",
    "میخوام سفارش بدم",
    "buy",
    "order",
}
CANCEL_KEYWORDS = {
    "لغو",
    "لغو سفارش",
    "انصراف",
    "cancel",
}

PHONE_RE = re.compile(r"(\+?98|0)?9\d{9}$")


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def _get_profile(user: User) -> dict[str, Any]:
    return user.profile_json or {}


def _set_profile(user: User, profile: dict[str, Any]) -> None:
    user.profile_json = profile


def _build_quick_reply(text: str) -> OutboundPlan:
    quick_replies = [
        QuickReplyOption(title="لغو سفارش", payload="لغو سفارش"),
    ]
    return OutboundPlan(type="quick_reply", text=text, quick_replies=quick_replies)


def _format_phone(text: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if digits.startswith("98"):
        digits = "0" + digits[2:]
    if not digits.startswith("0"):
        digits = "0" + digits
    if PHONE_RE.match(digits):
        return digits
    return None


async def handle_order_flow(
    session: AsyncSession,
    user: User,
    message_text: str | None,
) -> OutboundPlan | None:
    if not settings.ORDER_FORM_ENABLED:
        return None
    normalized = _normalize_text(message_text)
    if not normalized:
        return None

    profile = _get_profile(user)
    order_form = profile.get("order_form") if isinstance(profile, dict) else None

    if any(keyword in normalized for keyword in CANCEL_KEYWORDS):
        if order_form:
            profile.pop("order_form", None)
            _set_profile(user, profile)
            await session.commit()
        return OutboundPlan(type="text", text="سفارش لغو شد. اگر کمکی نیاز دارید بفرمایید.")

    if order_form and order_form.get("status") == "collecting":
        step = order_form.get("step", "name")
        data = order_form.get("data", {})

        if step == "name":
            if len(normalized) < 2:
                return _build_quick_reply("نام و نام خانوادگی را کامل وارد کنید.")
            data["name"] = message_text.strip()
            order_form["step"] = "phone"
            order_form["data"] = data
            profile["order_form"] = order_form
            _set_profile(user, profile)
            await session.commit()
            return _build_quick_reply("شماره موبایل را وارد کنید (مثال: 09123456789).")

        if step == "phone":
            phone = _format_phone(message_text)
            if not phone:
                return _build_quick_reply("شماره موبایل معتبر نیست. لطفاً دوباره وارد کنید.")
            data["phone"] = phone
            order_form["step"] = "address"
            order_form["data"] = data
            profile["order_form"] = order_form
            _set_profile(user, profile)
            await session.commit()
            return _build_quick_reply("آدرس کامل برای ارسال را وارد کنید.")

        if step == "address":
            if len(normalized) < 6:
                return _build_quick_reply("آدرس کامل‌تری ارسال کنید.")
            data["address"] = message_text.strip()
            order_form["step"] = "note"
            order_form["data"] = data
            profile["order_form"] = order_form
            _set_profile(user, profile)
            await session.commit()
            return _build_quick_reply("توضیح تکمیلی دارید؟ اگر ندارید بنویسید «ندارم».")

        if step == "note":
            note = message_text.strip()
            if note in {"ندارم", "خیر", "نه", "-"}:
                note = ""
            data["note"] = note
            order_form["status"] = "done"
            order_form["completed_at"] = utc_now().isoformat()
            order_form["data"] = data
            profile["order_form"] = order_form
            _set_profile(user, profile)
            await session.commit()
            summary = (
                "✅ اطلاعات سفارش ثبت شد:\n"
                f"- نام: {data.get('name')}\n"
                f"- موبایل: {data.get('phone')}\n"
                f"- آدرس: {data.get('address')}\n"
            )
            if data.get("note"):
                summary += f"- توضیح: {data.get('note')}\n"
            summary += "اگر محصول خاصی مدنظر دارید، نام یا لینک آن را ارسال کنید."
            return OutboundPlan(type="text", text=summary)

    if any(keyword in normalized for keyword in ORDER_KEYWORDS):
        profile["order_form"] = {
            "status": "collecting",
            "step": "name",
            "data": {},
            "started_at": utc_now().isoformat(),
        }
        _set_profile(user, profile)
        await session.commit()
        return _build_quick_reply("برای ثبت سفارش، نام و نام خانوادگی را ارسال کنید.")

    return None
