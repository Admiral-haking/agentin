#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

GENERIC_ASSISTANT_RE = re.compile(
    r"(چطور می.?توانم.*کمک|سوالی درباره محصولات|برای معرفی دقیق.?تر|به نظر می.?رسد که شما (عکسی|تصویری) ارسال کرده.?اید)",
    re.IGNORECASE,
)
IMAGE_BLIND_RE = re.compile(
    r"(نمی.?توانم|نمی.?تونم|can't|cannot).{0,24}(تصویر|عکس|image|photo)",
    re.IGNORECASE,
)


@dataclass
class Report:
    total_rows: int
    role_counts: dict[str, int]
    assistant_messages: int
    user_messages: int
    assistant_nonempty: int
    generic_assistant_messages: int
    image_blind_replies: int
    repeated_template_examples: list[dict[str, Any]]
    conversations_with_assistant_loops: int
    user_messages_followed_by_assistant: int
    recommendations: list[str]


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def analyze(csv_path: Path) -> Report:
    rows: list[dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)

    role_counts = Counter((row.get("role") or "").strip() for row in rows)
    assistant_rows = [row for row in rows if (row.get("role") or "").strip() == "assistant"]
    user_rows = [row for row in rows if (row.get("role") or "").strip() == "user"]
    assistant_texts = [
        _normalize(row.get("content_text") or "")
        for row in assistant_rows
        if _normalize(row.get("content_text") or "")
    ]

    generic_count = sum(1 for text in assistant_texts if GENERIC_ASSISTANT_RE.search(text))
    image_blind_count = sum(1 for text in assistant_texts if IMAGE_BLIND_RE.search(text))

    repeated_template_examples = [
        {"text": text[:220], "count": count}
        for text, count in Counter(assistant_texts).most_common(15)
        if count >= 3
    ][:8]

    by_conversation: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for row in rows:
        conversation_id = (row.get("conversation_id") or "").strip()
        try:
            row_id = int(row.get("id") or "0")
        except ValueError:
            continue
        by_conversation[conversation_id].append((row_id, row))
    for conversation_id in by_conversation:
        by_conversation[conversation_id].sort(key=lambda item: item[0])

    loop_conversations = 0
    for events in by_conversation.values():
        last_assistant = ""
        run_len = 0
        loop_found = False
        for _, row in events:
            if (row.get("role") or "").strip() != "assistant":
                continue
            text = _normalize(row.get("content_text") or "")
            if not text:
                continue
            if text == last_assistant:
                run_len += 1
                if run_len >= 2:
                    loop_found = True
            else:
                last_assistant = text
                run_len = 1
        if loop_found:
            loop_conversations += 1

    followed_count = 0
    total_user = 0
    for events in by_conversation.values():
        for index, (_, row) in enumerate(events):
            if (row.get("role") or "").strip() != "user":
                continue
            total_user += 1
            has_assistant_after = False
            for _, next_row in events[index + 1 : index + 6]:
                if (next_row.get("role") or "").strip() == "assistant":
                    has_assistant_after = True
                    break
            if has_assistant_after:
                followed_count += 1

    recommendations: list[str] = []
    assistant_nonempty = len(assistant_texts)
    generic_rate = (generic_count / assistant_nonempty) if assistant_nonempty else 0.0
    blind_rate = (image_blind_count / assistant_nonempty) if assistant_nonempty else 0.0
    if generic_rate >= 0.15:
        recommendations.append(
            "پاسخ‌های generic بالاست؛ بازنویسی contextual و تنوع لحن باید اجباری شود."
        )
    if blind_rate >= 0.03:
        recommendations.append(
            "در پاسخ تصویر، عبارت‌های «نمی‌توانم تصویر را ببینم» زیاد است؛ مسیر vision+product-match باید اولویت بگیرد."
        )
    if loop_conversations >= 5:
        recommendations.append(
            "loop مکالمه مشاهده شد؛ threshold تکرار و مسیر خروج انسانی باید سخت‌گیرانه‌تر شود."
        )
    if followed_count and total_user and (followed_count / total_user) < 0.9:
        recommendations.append(
            "بخشی از پیام‌های کاربر بی‌پاسخ مانده؛ مانیتور unresolved conversation و follow-up لازم است."
        )
    if not recommendations:
        recommendations.append("کیفیت مکالمه مناسب است؛ پایش هفتگی کافی است.")

    return Report(
        total_rows=len(rows),
        role_counts=dict(role_counts),
        assistant_messages=len(assistant_rows),
        user_messages=len(user_rows),
        assistant_nonempty=assistant_nonempty,
        generic_assistant_messages=generic_count,
        image_blind_replies=image_blind_count,
        repeated_template_examples=repeated_template_examples,
        conversations_with_assistant_loops=loop_conversations,
        user_messages_followed_by_assistant=followed_count,
        recommendations=recommendations,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze message export quality signals.")
    parser.add_argument("csv_path", type=Path, help="Path to messages.csv")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write JSON report",
    )
    args = parser.parse_args()

    report = analyze(args.csv_path)
    payload = asdict(report)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
