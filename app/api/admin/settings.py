from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_request_ip, require_role
from app.core.config import settings
from app.core.database import get_session
from app.models.bot_settings import BotSettings
from app.schemas.admin.settings import BotSettingsOut, BotSettingsUpdate
from app.services.audit import record_audit
from app.services.prompts import load_prompt

router = APIRouter(prefix="/admin/settings", tags=["admin"])


async def _get_or_create_settings(session: AsyncSession) -> BotSettings:
    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    settings_record = result.scalars().first()
    if settings_record:
        return settings_record

    system_prompt = load_prompt("system.txt")
    settings_record = BotSettings(
        ai_mode=settings.LLM_MODE,
        system_prompt=system_prompt,
        max_history_messages=settings.MAX_HISTORY_MESSAGES,
        max_output_chars=settings.MAX_RESPONSE_CHARS,
        language=settings.DEFAULT_LANGUAGE,
        active=True,
    )
    session.add(settings_record)
    await session.commit()
    return settings_record


@router.get("", response_model=BotSettingsOut)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> BotSettingsOut:
    settings_record = await _get_or_create_settings(session)
    return BotSettingsOut.model_validate(settings_record)


@router.put("", response_model=BotSettingsOut)
async def update_settings(
    payload: BotSettingsUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> BotSettingsOut:
    settings_record = await _get_or_create_settings(session)
    before = BotSettingsOut.model_validate(settings_record)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings_record, key, value)

    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="settings",
        action="update",
        before=before,
        after=settings_record,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return BotSettingsOut.model_validate(settings_record)
