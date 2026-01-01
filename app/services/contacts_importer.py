from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def _find_key(payload: dict[str, Any], candidates: list[str]) -> str | None:
    for key in candidates:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_contact(contact: dict[str, Any]) -> dict[str, Any] | None:
    external_id = _find_key(contact, ["external_id", "id", "user_id", "ig_id"])
    if not external_id:
        return None
    username = _find_key(contact, ["username", "user_name", "ig_username"])
    follow_status = _find_key(contact, ["follow_status", "status"])
    follower_count = _coerce_int(
        _find_key(contact, ["follower_count", "followers"])
    )
    return {
        "external_id": external_id,
        "username": username,
        "follow_status": follow_status,
        "follower_count": follower_count,
        "profile_json": contact,
    }


def extract_contacts_from_json(payload: Any) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("contacts")
    else:
        return contacts

    if not isinstance(items, list):
        return contacts

    for item in items:
        if isinstance(item, dict):
            contacts.append(item)
    return contacts


def parse_csv_contacts(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        return []
    return [row for row in reader if isinstance(row, dict)]


async def upsert_contact(
    session: AsyncSession,
    external_id: str,
    username: str | None,
    follow_status: str | None,
    follower_count: int | None,
    profile_json: dict | None,
    update_existing: bool = True,
) -> str:
    result = await session.execute(select(User).where(User.external_id == external_id))
    user = result.scalars().first()
    if user:
        if update_existing:
            user.username = username or user.username
            user.follow_status = follow_status or user.follow_status
            if follower_count is not None:
                user.follower_count = follower_count
            if profile_json is not None:
                user.profile_json = profile_json
            return "updated"
        return "skipped"

    user = User(
        external_id=external_id,
        username=username,
        follow_status=follow_status,
        follower_count=follower_count,
        profile_json=profile_json,
    )
    session.add(user)
    return "created"


async def upsert_contacts(
    session: AsyncSession,
    contacts: list[dict[str, Any]],
    update_existing: bool = True,
) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0

    for contact in contacts:
        normalized = normalize_contact(contact)
        if not normalized:
            skipped += 1
            continue
        result = await upsert_contact(
            session,
            external_id=normalized["external_id"],
            username=normalized.get("username"),
            follow_status=normalized.get("follow_status"),
            follower_count=normalized.get("follower_count"),
            profile_json=normalized.get("profile_json"),
            update_existing=update_existing,
        )
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
        else:
            skipped += 1

    await session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def parse_json_contacts(content: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []
    return extract_contacts_from_json(payload)
