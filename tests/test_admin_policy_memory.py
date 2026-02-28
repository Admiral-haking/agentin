import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("DIRECTAM_BASE_URL", "https://directam.example.com")
os.environ.setdefault("SERVICE_API_KEY", "test")

from app.services.admin_policy_memory import (
    AdminPolicyMemoryItem,
    format_admin_policy_memory,
    parse_policy_memory_entry,
)


def test_parse_policy_memory_detects_priority_and_kind() -> None:
    entry = parse_policy_memory_entry(
        "قانون: کمپین نوروز فوری است و باید کد تخفیف اعمال شود.",
        source="admin_api",
    )
    assert entry is not None
    assert entry.priority == "critical"
    assert entry.kind == "campaign"
    assert entry.source == "admin_api"


def test_parse_policy_memory_ignores_non_policy_text() -> None:
    entry = parse_policy_memory_entry("سلام، امروز چند فروش داشتیم؟")
    assert entry is None


def test_format_policy_memory_builds_priority_lines() -> None:
    items = [
        AdminPolicyMemoryItem(
            text="ارسال سفارشات ایونت باید فوری انجام شود.",
            priority="critical",
            kind="event",
            source="admin_webhook",
            created_at=datetime(2026, 2, 28, 10, 30, tzinfo=timezone.utc),
        ),
        AdminPolicyMemoryItem(
            text="در پاسخ فروش، لینک محصول باید ارائه شود.",
            priority="high",
            kind="rule",
            source="admin_webhook",
            created_at=datetime(2026, 2, 27, 14, 0, tzinfo=timezone.utc),
        ),
    ]
    formatted = format_admin_policy_memory(items)
    assert formatted is not None
    assert "CRITICAL|event|" in formatted
    assert "HIGH|rule|" in formatted
    assert "لینک محصول باید ارائه شود" in formatted
