from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.agent_trace import build_agent_trace_turns


def _ts(base: datetime, seconds: int) -> datetime:
    return base + timedelta(seconds=seconds)


def test_build_agent_trace_turns_groups_decisions_per_response() -> None:
    base = datetime(2026, 2, 28, 10, 0, tzinfo=timezone.utc)
    messages = [
        SimpleNamespace(
            id=1,
            role="user",
            type="text",
            content_text="بوت میخوام",
            media_url=None,
            created_at=_ts(base, 1),
        ),
        SimpleNamespace(
            id=2,
            role="user",
            type="text",
            content_text="چرا جواب تکراریه؟",
            media_url=None,
            created_at=_ts(base, 18),
        ),
    ]
    logs = [
        SimpleNamespace(
            event_type="intent_detected",
            message=None,
            data={"intent": "product_search", "conversation_id": 5},
            created_at=_ts(base, 2),
        ),
        SimpleNamespace(
            event_type="product_matched",
            message=None,
            data={"matched_count": 3, "conversation_id": 5},
            created_at=_ts(base, 3),
        ),
        SimpleNamespace(
            event_type="reply_rewritten_by_guardrail",
            message=None,
            data={"reasons": ["generic_reply_rewritten"], "conversation_id": 5},
            created_at=_ts(base, 4),
        ),
        SimpleNamespace(
            event_type="assistant_response",
            message="چند مدل نزدیک پیدا شد.",
            data={"intent": "llm", "conversation_id": 5},
            created_at=_ts(base, 5),
        ),
        SimpleNamespace(
            event_type="intent_detected",
            message=None,
            data={"intent": "support", "conversation_id": 5},
            created_at=_ts(base, 19),
        ),
        SimpleNamespace(
            event_type="loop_detected",
            message=None,
            data={
                "conversation_id": 5,
                "loop_counter": 3,
                "reason": "loop_repeated_recent_cycle",
            },
            created_at=_ts(base, 20),
        ),
        SimpleNamespace(
            event_type="loop_escalated_to_operator",
            message=None,
            data={"conversation_id": 5, "ticket_id": 77},
            created_at=_ts(base, 21),
        ),
        SimpleNamespace(
            event_type="assistant_response",
            message="گفتگو به اپراتور ارجاع شد.",
            data={"intent": "llm", "conversation_id": 5, "ticket_id": 77},
            created_at=_ts(base, 22),
        ),
    ]

    turns = build_agent_trace_turns(logs=logs, messages=messages, limit_turns=5)

    assert len(turns) == 2
    assert turns[0]["decision_summary"]["intent"] == "product_search"
    assert turns[0]["decision_summary"]["matched_count"] == 3
    assert "generic_reply_rewritten" in turns[0]["decision_summary"]["guardrail_reasons"]
    assert turns[1]["decision_summary"]["intent"] == "support"
    assert turns[1]["decision_summary"]["ticket_id"] == 77
    assert turns[1]["decision_summary"]["auto_escalated"] is True
    assert turns[1]["assistant_response"]["ticket_id"] == 77


def test_build_agent_trace_turns_honors_limit() -> None:
    base = datetime(2026, 2, 28, 11, 0, tzinfo=timezone.utc)
    messages = []
    logs = [
        SimpleNamespace(
            event_type="assistant_response",
            message=f"reply-{index}",
            data={"conversation_id": 9},
            created_at=_ts(base, index),
        )
        for index in range(1, 5)
    ]

    turns = build_agent_trace_turns(logs=logs, messages=messages, limit_turns=2)

    assert len(turns) == 2
    assert turns[0]["assistant_response"]["text"] == "reply-3"
    assert turns[1]["assistant_response"]["text"] == "reply-4"
