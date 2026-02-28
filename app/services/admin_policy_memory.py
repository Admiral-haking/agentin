from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_log import AppLog
from app.services.app_log_store import log_event

_MAX_TEXT_LEN = 1200

_POLICY_MARKERS = (
    "#policy",
    "#rule",
    "#event",
    "#campaign",
    "policy:",
    "rule:",
    "event:",
    "campaign:",
    "سیاست:",
    "قانون:",
    "دستور:",
    "ایونت:",
    "کمپین:",
)

_RULE_KEYWORDS = {
    "قانون",
    "سیاست",
    "دستور",
    "الزامی",
    "ممنوع",
    "حتما",
    "باید",
}
_EVENT_KEYWORDS = {"ایونت", "رویداد", "قرعه", "جشنواره", "winner", "برنده"}
_CAMPAIGN_KEYWORDS = {"کمپین", "تخفیف", "discount", "کد", "کد تخفیف", "promo"}

_PRIORITY_CRITICAL = {"p0", "critical", "urgent", "فوری", "ضروری", "خیلی مهم"}
_PRIORITY_HIGH = {"p1", "high", "مهم"}

_PRIORITY_SCORE = {"critical": 3, "high": 2, "normal": 1}


@dataclass(frozen=True)
class AdminPolicyMemoryItem:
    text: str
    priority: str
    kind: str
    source: str
    created_at: datetime | None
    conversation_id: int | None = None
    message_id: int | None = None


def _normalize_space(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split()).strip()


def _normalized_key(text: str) -> str:
    normalized = _normalize_space(text).lower()
    normalized = re.sub(r"[^\w\u0600-\u06FF ]+", "", normalized)
    return " ".join(normalized.split())


def _detect_priority(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in _PRIORITY_CRITICAL):
        return "critical"
    if any(token in lowered for token in _PRIORITY_HIGH):
        return "high"
    return "normal"


def _detect_kind(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in _CAMPAIGN_KEYWORDS):
        return "campaign"
    if any(token in lowered for token in _EVENT_KEYWORDS):
        return "event"
    if any(token in lowered for token in _RULE_KEYWORDS):
        return "rule"
    return "note"


def _is_policy_message(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in _POLICY_MARKERS):
        return True
    keyword_hits = 0
    for token in (_RULE_KEYWORDS | _EVENT_KEYWORDS | _CAMPAIGN_KEYWORDS):
        if token in lowered:
            keyword_hits += 1
    return len(text) >= 18 and keyword_hits >= 2


def parse_policy_memory_entry(
    text: str | None,
    *,
    source: str = "admin_webhook",
    priority_override: str | None = None,
    kind_override: str | None = None,
    conversation_id: int | None = None,
    message_id: int | None = None,
) -> AdminPolicyMemoryItem | None:
    cleaned = _normalize_space(text)
    if not cleaned:
        return None
    if not _is_policy_message(cleaned):
        return None
    priority = (priority_override or _detect_priority(cleaned)).strip().lower()
    if priority not in _PRIORITY_SCORE:
        priority = "normal"
    kind = (kind_override or _detect_kind(cleaned)).strip().lower()
    if kind not in {"rule", "event", "campaign", "note"}:
        kind = "note"
    return AdminPolicyMemoryItem(
        text=cleaned[:_MAX_TEXT_LEN],
        priority=priority,
        kind=kind,
        source=source,
        created_at=None,
        conversation_id=conversation_id,
        message_id=message_id,
    )


async def _last_reset_ts(session: AsyncSession) -> datetime | None:
    reset_query = (
        select(AppLog.created_at)
        .where(AppLog.event_type == "admin_policy_memory_reset")
        .order_by(AppLog.created_at.desc())
        .limit(1)
    )
    return (await session.execute(reset_query)).scalars().first()


async def get_admin_policy_memory(
    session: AsyncSession,
    *,
    limit: int = 12,
) -> list[AdminPolicyMemoryItem]:
    if limit <= 0:
        return []
    since_reset = await _last_reset_ts(session)
    query = (
        select(AppLog)
        .where(AppLog.event_type == "admin_policy_memory_set")
        .order_by(AppLog.created_at.desc())
        .limit(250)
    )
    if since_reset is not None:
        query = query.where(AppLog.created_at >= since_reset)

    rows = (await session.execute(query)).scalars().all()
    items: list[AdminPolicyMemoryItem] = []
    seen: set[str] = set()
    for row in rows:
        data = row.data if isinstance(row.data, dict) else {}
        text = _normalize_space(data.get("text") or row.message or "")
        if not text:
            continue
        dedupe_key = _normalized_key(text)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        priority = str(data.get("priority") or "normal").lower()
        if priority not in _PRIORITY_SCORE:
            priority = "normal"
        kind = str(data.get("kind") or "note").lower()
        if kind not in {"rule", "event", "campaign", "note"}:
            kind = "note"
        source = str(data.get("source") or "admin_webhook")
        items.append(
            AdminPolicyMemoryItem(
                text=text,
                priority=priority,
                kind=kind,
                source=source,
                created_at=row.created_at,
                conversation_id=data.get("conversation_id")
                if isinstance(data.get("conversation_id"), int)
                else None,
                message_id=data.get("message_id")
                if isinstance(data.get("message_id"), int)
                else None,
            )
        )

    items.sort(
        key=lambda item: (
            _PRIORITY_SCORE.get(item.priority, 1),
            item.created_at or datetime.min,
        ),
        reverse=True,
    )
    return items[:limit]


async def store_admin_policy_memory(
    session: AsyncSession,
    *,
    text: str | None,
    source: str = "admin_webhook",
    priority_override: str | None = None,
    kind_override: str | None = None,
    conversation_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    entry = parse_policy_memory_entry(
        text,
        source=source,
        priority_override=priority_override,
        kind_override=kind_override,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    if entry is None:
        return False

    recent = await get_admin_policy_memory(session, limit=40)
    new_key = _normalized_key(entry.text)
    if any(_normalized_key(item.text) == new_key for item in recent):
        return False

    await log_event(
        session,
        level="info",
        event_type="admin_policy_memory_set",
        message=entry.text[:240],
        data={
            "text": entry.text,
            "priority": entry.priority,
            "kind": entry.kind,
            "source": entry.source,
            "conversation_id": conversation_id,
            "message_id": message_id,
        },
        commit=False,
    )
    return True


async def reset_admin_policy_memory(
    session: AsyncSession,
    *,
    source: str = "admin_panel",
) -> None:
    await log_event(
        session,
        level="info",
        event_type="admin_policy_memory_reset",
        message="policy memory reset",
        data={"source": source},
        commit=False,
    )


def format_admin_policy_memory(items: list[AdminPolicyMemoryItem]) -> str | None:
    if not items:
        return None
    lines: list[str] = []
    for item in items:
        stamp = (
            item.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
            if item.created_at is not None
            else "-"
        )
        lines.append(
            f"- ({item.priority.upper()}|{item.kind}|{stamp}) {item.text}"
        )
    return "\n".join(lines[:12])
