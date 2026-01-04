from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.behavior_event import BehaviorEvent
from app.models.user_behavior_profile import UserBehaviorProfile
from app.services.behavior_analyzer import BehaviorMatch
from app.utils.time import utc_now


async def upsert_behavior_profile(
    session: AsyncSession,
    user_id: int,
    conversation_id: int | None,
    match: BehaviorMatch | None,
    last_message: str | None,
    summary_counts: dict[str, int] | None = None,
    recent_payload: list[dict[str, Any]] | None = None,
) -> UserBehaviorProfile:
    profile = await session.get(UserBehaviorProfile, user_id)
    if not profile:
        profile = UserBehaviorProfile(user_id=user_id)
        session.add(profile)

    history: list[dict[str, Any]] = []
    if isinstance(profile.pattern_history, list):
        history = list(profile.pattern_history)

    if match:
        history.append(
            {
                "pattern": match.pattern,
                "confidence": match.confidence,
                "reason": match.reason,
                "keywords": list(match.keywords),
                "tags": list(match.tags),
                "created_at": utc_now().isoformat(),
            }
        )

    if recent_payload:
        history = history[-settings.BEHAVIOR_HISTORY_LIMIT :]
    elif history:
        history = history[-settings.BEHAVIOR_HISTORY_LIMIT :]

    if match:
        profile.last_pattern = match.pattern
        profile.confidence = match.confidence
    profile.last_seen_at = utc_now()
    profile.pattern_history = history

    await session.flush()

    if match:
        session.add(
            BehaviorEvent(
                user_id=user_id,
                conversation_id=conversation_id,
                pattern=match.pattern,
                confidence=match.confidence,
                reason=match.reason,
                keywords=list(match.keywords),
                tags=list(match.tags),
            )
        )

    await session.commit()
    return profile


async def get_behavior_profile(
    session: AsyncSession,
    user_id: int,
) -> UserBehaviorProfile | None:
    return await session.get(UserBehaviorProfile, user_id)


def build_behavior_snapshot(
    profile: UserBehaviorProfile | None,
    last_message: str | None,
    summary_counts: dict[str, int] | None = None,
    recent_payload: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not profile:
        return None
    snapshot: dict[str, Any] = {
        "last_pattern": profile.last_pattern,
        "confidence": profile.confidence,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "last_message": (last_message or "")[:500],
        "summary": summary_counts or {},
        "recent": recent_payload or [],
    }
    return snapshot
