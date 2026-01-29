from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_media_note import AdminMediaNote


async def create_admin_media_note(
    session: AsyncSession,
    conversation_id: int,
    media_url: str,
    *,
    message_id: int | None = None,
    tag: str | None = None,
    category: str | None = None,
) -> AdminMediaNote:
    note = AdminMediaNote(
        conversation_id=conversation_id,
        message_id=message_id,
        media_url=media_url,
        tag=tag,
        category=category,
    )
    session.add(note)
    await session.commit()
    return note


async def get_recent_admin_media_notes(
    session: AsyncSession,
    conversation_id: int,
    limit: int = 3,
) -> list[AdminMediaNote]:
    result = await session.execute(
        select(AdminMediaNote)
        .where(AdminMediaNote.conversation_id == conversation_id)
        .order_by(AdminMediaNote.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def format_admin_media_notes(notes: Iterable[AdminMediaNote]) -> str | None:
    lines: list[str] = []
    for note in notes:
        parts = [note.media_url]
        if note.category:
            parts.append(f"category={note.category}")
        if note.tag:
            parts.append(f"tag={note.tag}")
        lines.append(" | ".join(parts))
    if not lines:
        return None
    return "\n".join(lines)
