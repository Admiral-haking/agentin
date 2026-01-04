from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.campaign import Campaign
from app.models.faq import Faq
from app.models.message import Message
from app.models.user import User
from app.utils.time import utc_now


@dataclass(frozen=True)
class ContextBundle:
    system_prompt: str
    sections: dict[str, str]


def _format_section(title: str, body: str | None) -> str | None:
    if not body:
        return None
    return f"[{title}]\n{body.strip()}"


def format_campaigns(campaigns: list[Campaign]) -> str | None:
    if not campaigns:
        return None
    lines = []
    for campaign in campaigns:
        parts = [campaign.title, campaign.body]
        if campaign.discount_code:
            parts.append(f"کد تخفیف: {campaign.discount_code}")
        if campaign.link:
            parts.append(f"لینک: {campaign.link}")
        lines.append(" | ".join(part for part in parts if part))
    if not lines:
        return None
    return "\n".join(f"- {line}" for line in lines)


def format_faqs(faqs: list[Faq]) -> str | None:
    if not faqs:
        return None
    lines = [
        f"Q: {faq.question}\nA: {faq.answer}"
        for faq in faqs
        if faq.question and faq.answer
    ]
    if not lines:
        return None
    return "\n".join(lines)


def format_recent_messages(history: list[Message], limit: int = 6) -> str | None:
    if not history:
        return None
    items = []
    for msg in history[-limit:]:
        if msg.role not in {"user", "assistant"} or msg.type == "read":
            continue
        text = msg.content_text or f"[{msg.type}]"
        items.append(f"{msg.role}: {text}")
    if not items:
        return None
    return "\n".join(items)


def format_user_profile(user: User, behavior_snapshot: dict[str, Any] | None) -> str | None:
    bits = []
    if user.username:
        bits.append(f"username={user.username}")
    if user.follow_status:
        bits.append(f"follow_status={user.follow_status}")
    if user.follower_count is not None:
        bits.append(f"follower_count={user.follower_count}")
    if user.is_vip:
        bits.append("vip=true")
    if user.vip_score:
        bits.append(f"vip_score={user.vip_score}")
    prefs = None
    if isinstance(user.profile_json, dict):
        prefs = user.profile_json.get("prefs")
    if isinstance(prefs, dict) and prefs:
        pref_bits = []
        for key in ("categories", "gender", "sizes", "colors", "budget_min", "budget_max"):
            value = prefs.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                if value:
                    pref_bits.append(f"{key}={', '.join(str(item) for item in value)}")
            else:
                pref_bits.append(f"{key}={value}")
        if pref_bits:
            bits.append("prefs=" + "; ".join(pref_bits))
    if behavior_snapshot:
        bits.append(f"behavior={behavior_snapshot.get('last_pattern')}")
        bits.append(f"confidence={behavior_snapshot.get('confidence')}")
    if not bits:
        return None
    return " | ".join(bits)


def format_behavior_detail(behavior_snapshot: dict[str, Any] | None) -> str | None:
    if not behavior_snapshot:
        return None
    lines = []
    if behavior_snapshot.get("last_pattern"):
        lines.append(
            f"آخرین الگو: {behavior_snapshot.get('last_pattern')} (confidence={behavior_snapshot.get('confidence')})"
        )
    if behavior_snapshot.get("last_message"):
        lines.append(f"آخرین پیام: {behavior_snapshot.get('last_message')}")
    summary = behavior_snapshot.get("summary") or {}
    if isinstance(summary, dict) and summary:
        top = sorted(summary.items(), key=lambda item: item[1], reverse=True)[:5]
        lines.append("خلاصه: " + "، ".join(f"{k}({v})" for k, v in top))
    recent = behavior_snapshot.get("recent") or []
    if isinstance(recent, list) and recent:
        lines.append("نمونه‌های اخیر: " + "، ".join(
            f"{item.get('pattern')}({item.get('confidence')})" for item in recent if isinstance(item, dict)
        ))
    return "\n".join(line for line in lines if line)


def format_conversation_state(state_payload: dict[str, Any] | None) -> str | None:
    if not state_payload:
        return None
    lines = []
    for key in (
        "intent",
        "category",
        "slots_required",
        "slots_filled",
        "selected_product",
        "last_user_question",
        "last_bot_action",
        "last_bot_answer_by_intent",
        "last_user_message_id",
        "last_updated_at",
    ):
        value = state_payload.get(key)
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def build_context_bundle(
    base_prompt: str,
    store_text: str | None,
    campaigns: list[Campaign] | None = None,
    faqs: list[Faq] | None = None,
    catalog_summary: str | None = None,
    behavior_snapshot: dict[str, Any] | None = None,
    conversation_state: dict[str, Any] | None = None,
    recent_messages: list[Message] | None = None,
    user: User | None = None,
    admin_notes: str | None = None,
    response_log_summary: str | None = None,
) -> ContextBundle:
    sections: dict[str, str] = {}
    system_parts: list[str] = [base_prompt]

    store_section = _format_section("STORE", store_text or "")
    if store_section:
        system_parts.append(store_section)
        sections["store"] = store_section

    campaigns_section = _format_section("ACTIVE CAMPAIGNS", format_campaigns(campaigns or []))
    if campaigns_section:
        system_parts.append(campaigns_section)
        sections["campaigns"] = campaigns_section

    faqs_section = _format_section("VERIFIED FAQs", format_faqs(faqs or []))
    if faqs_section:
        system_parts.append(faqs_section)
        sections["faqs"] = faqs_section

    if catalog_summary:
        system_parts.append(catalog_summary)
        sections["catalog"] = catalog_summary

    if user:
        profile_text = format_user_profile(user, behavior_snapshot)
        if profile_text:
            profile_section = _format_section("USER_PROFILE + BEHAVIOR", profile_text)
            if profile_section:
                system_parts.append(profile_section)
                sections["user_profile"] = profile_section

    behavior_detail = format_behavior_detail(behavior_snapshot)
    if behavior_detail:
        behavior_section = _format_section("BEHAVIOR", behavior_detail)
        if behavior_section:
            system_parts.append(behavior_section)
            sections["behavior"] = behavior_section

    state_section = _format_section("CONVERSATION_STATE", format_conversation_state(conversation_state))
    if state_section:
        system_parts.append(state_section)
        sections["conversation_state"] = state_section

    recent_section = _format_section("RECENT_MESSAGES", format_recent_messages(recent_messages or []))
    if recent_section:
        system_parts.append(recent_section)
        sections["recent_messages"] = recent_section

    if admin_notes:
        notes_section = _format_section("ADMIN NOTES", admin_notes)
        if notes_section:
            system_parts.append(notes_section)
            sections["admin_notes"] = notes_section

    if response_log_summary:
        system_parts.append(response_log_summary)
        sections["recent_responses"] = response_log_summary

    system_prompt = "\n\n".join(part for part in system_parts if part).strip()
    sections["system_prompt"] = base_prompt

    return ContextBundle(system_prompt=system_prompt, sections=sections)
