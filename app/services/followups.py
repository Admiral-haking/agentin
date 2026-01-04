from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.bot_settings import BotSettings
from app.models.conversation import Conversation
from app.models.followup_task import FollowupTask
from app.models.message import Message
from app.models.user import User
from app.services.app_log_store import log_event
from app.services.sender import Sender, SenderError
from app.utils.time import utc_now


@dataclass(frozen=True)
class FollowupConfig:
    enabled: bool
    delay_hours: int
    poll_sec: int
    message: str


def _extract_followup_config(settings_record: BotSettings | None) -> FollowupConfig:
    if settings_record and settings_record.followup_enabled is not None:
        enabled = settings_record.followup_enabled
        delay_hours = settings_record.followup_delay_hours or settings.FOLLOWUP_DELAY_HOURS
        poll_sec = settings.FOLLOWUP_POLL_SEC
        message = settings_record.followup_message or settings.FOLLOWUP_MESSAGE
    else:
        enabled = settings.FOLLOWUP_ENABLED
        delay_hours = settings.FOLLOWUP_DELAY_HOURS
        poll_sec = settings.FOLLOWUP_POLL_SEC
        message = settings.FOLLOWUP_MESSAGE
    return FollowupConfig(
        enabled=bool(enabled),
        delay_hours=int(delay_hours),
        poll_sec=int(poll_sec),
        message=message,
    )


async def get_followup_config(session: AsyncSession) -> FollowupConfig:
    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    settings_record = result.scalars().first()
    return _extract_followup_config(settings_record)


async def schedule_followup_task(
    session: AsyncSession,
    conversation: Conversation,
    user: User,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> FollowupTask | None:
    config = await get_followup_config(session)
    if not config.enabled:
        return None
    if user.followup_opt_out:
        return None

    existing = await session.execute(
        select(FollowupTask)
        .where(FollowupTask.conversation_id == conversation.id)
        .where(FollowupTask.status == "scheduled")
        .order_by(FollowupTask.scheduled_for.desc())
        .limit(1)
    )
    if existing.scalars().first():
        return None

    scheduled_for = utc_now() + timedelta(hours=config.delay_hours)
    task = FollowupTask(
        user_id=user.id,
        conversation_id=conversation.id,
        status="scheduled",
        scheduled_for=scheduled_for,
        reason=reason,
        payload=payload or {"text": config.message},
    )
    session.add(task)
    await session.commit()
    await log_event(
        session,
        level="info",
        event_type="followup_scheduled",
        data={
            "conversation_id": conversation.id,
            "user_id": user.id,
            "scheduled_for": scheduled_for.isoformat(),
            "reason": reason,
        },
    )
    return task


async def cancel_followups_for_conversation(
    session: AsyncSession,
    conversation_id: int,
    reason: str,
) -> int:
    result = await session.execute(
        select(FollowupTask)
        .where(FollowupTask.conversation_id == conversation_id)
        .where(FollowupTask.status == "scheduled")
    )
    tasks = list(result.scalars().all())
    if not tasks:
        return 0
    for task in tasks:
        task.status = "cancelled"
        task.reason = reason
    await session.commit()
    await log_event(
        session,
        level="info",
        event_type="followup_cancelled",
        data={
            "conversation_id": conversation_id,
            "count": len(tasks),
            "reason": reason,
        },
    )
    return len(tasks)


async def _within_window(session: AsyncSession, conversation_id: int) -> bool:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation or not conversation.last_user_message_at:
        return False
    delta = utc_now() - conversation.last_user_message_at
    return delta.total_seconds() <= settings.WINDOW_HOURS * 3600


async def _send_followup(
    session: AsyncSession,
    task: FollowupTask,
    message_text: str,
) -> bool:
    user = await session.get(User, task.user_id)
    if not user or not user.external_id:
        task.status = "failed"
        await session.commit()
        return False
    if not await _within_window(session, task.conversation_id or 0):
        task.status = "skipped"
        await session.commit()
        return False
    sender = Sender()
    try:
        response = await sender.send_text(user.external_id, message_text)
        message_id = response.get("message_id") if isinstance(response, dict) else None
    except SenderError as exc:
        task.status = "failed"
        await session.commit()
        await log_event(
            session,
            level="error",
            event_type="followup_failed",
            message=str(exc),
            data={"task_id": task.id},
        )
        return False

    task.status = "sent"
    task.sent_at = utc_now()
    await session.commit()
    await log_event(
        session,
        level="info",
        event_type="followup_sent",
        message=message_text,
        data={
            "task_id": task.id,
            "conversation_id": task.conversation_id,
            "message_id": message_id,
        },
    )

    if task.conversation_id:
        conversation = await session.get(Conversation, task.conversation_id)
        if conversation:
            conversation.last_bot_message_at = utc_now()
    if task.conversation_id:
        message = Message(
            conversation_id=task.conversation_id,
            role="assistant",
            type="text",
            content_text=message_text,
        )
        session.add(message)
        await session.commit()
    return True


async def followup_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        async with AsyncSessionLocal() as session:
            config = await get_followup_config(session)
            if not config.enabled:
                await asyncio.sleep(config.poll_sec)
                continue
            now = utc_now()
            result = await session.execute(
                select(FollowupTask)
                .where(FollowupTask.status == "scheduled")
                .where(FollowupTask.scheduled_for <= now)
                .order_by(FollowupTask.scheduled_for.asc())
                .limit(20)
            )
            tasks = list(result.scalars().all())
            for task in tasks:
                payload = task.payload if isinstance(task.payload, dict) else {}
                message_text = payload.get("text") or config.message
                await _send_followup(session, task, message_text)
        await asyncio.sleep(max(5, settings.FOLLOWUP_POLL_SEC))
