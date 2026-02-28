from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.app_log import AppLog
from app.models.message import Message


def _iso(value: datetime | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _window_contains(
    timestamp: datetime | None,
    start_exclusive: datetime | None,
    end_inclusive: datetime | None,
) -> bool:
    if not isinstance(timestamp, datetime):
        return False
    if isinstance(start_exclusive, datetime) and timestamp <= start_exclusive:
        return False
    if isinstance(end_inclusive, datetime) and timestamp > end_inclusive:
        return False
    return True


def _clean_data(data: Any) -> dict[str, Any]:
    return data if isinstance(data, dict) else {}


def _compact_data(data: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "intent",
        "category",
        "provider",
        "latency_ms",
        "matched_count",
        "suggest_count",
        "loop_counter",
        "reason",
        "ticket_id",
        "plan_type",
        "source",
        "message_type",
        "reasons",
        "product_ids",
        "product_slugs",
    )
    compact: dict[str, Any] = {}
    for key in keep_keys:
        value = data.get(key)
        if value in (None, "", [], {}):
            continue
        compact[key] = value
    return compact


def _serialize_event(log: AppLog, include_debug_data: bool) -> dict[str, Any]:
    data = _clean_data(log.data)
    payload: dict[str, Any] = {
        "event_type": log.event_type,
        "created_at": _iso(log.created_at),
    }
    if log.message:
        payload["message"] = log.message
    event_data = data if include_debug_data else _compact_data(data)
    if event_data:
        payload["data"] = event_data
    return payload


def _serialize_message(msg: Message) -> dict[str, Any]:
    return {
        "id": msg.id,
        "role": msg.role,
        "type": msg.type,
        "text": msg.content_text,
        "media_url": msg.media_url,
        "created_at": _iso(msg.created_at),
    }


def _summarize_turn(decision_logs: list[AppLog]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "events_count": len(decision_logs),
        "event_chain": [log.event_type for log in decision_logs],
    }
    guardrail_reasons: list[str] = []
    for log in decision_logs:
        data = _clean_data(log.data)
        if log.event_type == "intent_detected" and isinstance(data.get("intent"), str):
            summary["intent"] = data.get("intent")
        if log.event_type == "provider_selected" and isinstance(data.get("provider"), str):
            summary["provider"] = data.get("provider")
        if log.event_type == "llm_latency" and isinstance(data.get("latency_ms"), int):
            summary["latency_ms"] = data.get("latency_ms")
        if log.event_type == "product_matched" and isinstance(data.get("matched_count"), int):
            summary["matched_count"] = data.get("matched_count")
        if log.event_type == "loop_detected":
            summary["loop_counter"] = data.get("loop_counter")
            summary["loop_reason"] = data.get("reason")
        if log.event_type in {"ticket_created", "loop_escalated_to_operator"}:
            ticket_id = data.get("ticket_id")
            if isinstance(ticket_id, int):
                summary["ticket_id"] = ticket_id
                summary["auto_escalated"] = log.event_type == "loop_escalated_to_operator"
        if log.event_type == "reply_rewritten_by_guardrail":
            reasons = data.get("reasons")
            if isinstance(reasons, list):
                for reason in reasons:
                    if isinstance(reason, str) and reason.strip():
                        guardrail_reasons.append(reason.strip())
    if guardrail_reasons:
        summary["guardrail_reasons"] = list(dict.fromkeys(guardrail_reasons))
    return summary


def build_agent_trace_turns(
    *,
    logs: list[AppLog],
    messages: list[Message],
    limit_turns: int,
    include_debug_data: bool = False,
) -> list[dict[str, Any]]:
    if limit_turns <= 0:
        return []

    ordered_logs = sorted(
        logs,
        key=lambda item: item.created_at or datetime.min,
    )
    ordered_messages = sorted(
        messages,
        key=lambda item: item.created_at or datetime.min,
    )
    assistant_responses = [
        log for log in ordered_logs if log.event_type == "assistant_response"
    ]
    if not assistant_responses:
        return []

    start_index = max(0, len(assistant_responses) - limit_turns)
    selected_responses = assistant_responses[start_index:]
    turns: list[dict[str, Any]] = []

    for offset, response_log in enumerate(selected_responses, start=1):
        global_index = start_index + offset - 1
        prev_response = (
            assistant_responses[global_index - 1] if global_index > 0 else None
        )
        window_start = prev_response.created_at if prev_response else None
        window_end = response_log.created_at

        decision_logs = [
            log
            for log in ordered_logs
            if log.event_type != "assistant_response"
            and _window_contains(log.created_at, window_start, window_end)
        ]
        user_messages = [
            _serialize_message(msg)
            for msg in ordered_messages
            if msg.role == "user"
            and _window_contains(msg.created_at, window_start, window_end)
        ]
        admin_messages = [
            _serialize_message(msg)
            for msg in ordered_messages
            if msg.role == "admin"
            and _window_contains(msg.created_at, window_start, window_end)
        ]
        response_data = _clean_data(response_log.data)
        assistant_payload: dict[str, Any] = {
            "created_at": _iso(response_log.created_at),
            "text": response_log.message,
            "source": response_data.get("source"),
            "intent": response_data.get("intent"),
            "message_type": response_data.get("message_type"),
            "ticket_id": response_data.get("ticket_id")
            if isinstance(response_data.get("ticket_id"), int)
            else None,
        }
        if include_debug_data and response_data:
            assistant_payload["data"] = response_data

        turns.append(
            {
                "turn": offset,
                "window": {
                    "from": _iso(window_start),
                    "to": _iso(window_end),
                },
                "user_messages": user_messages,
                "admin_messages": admin_messages,
                "assistant_response": assistant_payload,
                "decision_chain": [
                    _serialize_event(log, include_debug_data)
                    for log in decision_logs
                ],
                "decision_summary": _summarize_turn(decision_logs),
            }
        )

    return turns
