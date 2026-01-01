from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.user import User
from app.schemas.send import Button, QuickReplyOption, TemplateElement
from app.services.app_log_store import log_event

router = APIRouter(prefix="/api", tags=["service"])


class InvalidApiTokenError(Exception):
    def __init__(self, api_token: str) -> None:
        super().__init__("Invalid API token")
        self.api_token = api_token


def require_service_key(api_key: str | None = Header(default=None)) -> None:
    token = api_key or ""
    if token != settings.SERVICE_API_KEY:
        raise InvalidApiTokenError(token)


class TextPayload(BaseModel):
    receiver_id: str
    text: str


class ButtonTextPayload(BaseModel):
    receiver_id: str
    text: str
    buttons: list[Button]


class QuickReplyPayload(BaseModel):
    receiver_id: str
    text: str
    quick_replies: list[QuickReplyOption]


class GenericTemplatePayload(BaseModel):
    receiver_id: str
    elements: list[TemplateElement]


class PhotoPayload(BaseModel):
    receiver_id: str
    image_url: str


class VideoPayload(BaseModel):
    receiver_id: str
    video_url: str


class AudioPayload(BaseModel):
    receiver_id: str
    audio_url: str


class UserLookupPayload(BaseModel):
    user_id: str


async def _log_stub(
    session: AsyncSession,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    await log_event(
        session,
        level="info",
        event_type=event_type,
        data=payload,
        commit=True,
    )


def _success_response(message: str) -> dict:
    return {
        "success": True,
        "message": message,
        "message_id": uuid4().hex,
    }


@router.post("/send/text")
async def send_text(
    payload: TextPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_text", payload.model_dump())
    return _success_response("Message sent successfully")


@router.post("/send/button-text")
async def send_button_text(
    payload: ButtonTextPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_button_text", payload.model_dump())
    return _success_response("Message sent successfully")


@router.post("/send/quick-reply")
async def send_quick_reply(
    payload: QuickReplyPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_quick_reply", payload.model_dump())
    return _success_response("Message sent successfully")


@router.post("/send/generic-template")
async def send_generic_template(
    payload: GenericTemplatePayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_generic_template", payload.model_dump())
    return _success_response("Message sent successfully")


@router.post("/send/photo")
async def send_photo(
    payload: PhotoPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_photo", payload.model_dump())
    return _success_response("Photo sent successfully")


@router.post("/send/video")
async def send_video(
    payload: VideoPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_video", payload.model_dump())
    return _success_response("Video sent successfully")


@router.post("/send/audio")
async def send_audio(
    payload: AudioPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    await _log_stub(session, "send_audio", payload.model_dump())
    return _success_response("Message sent successfully")


@router.post("/instagram-user/username")
async def instagram_username(
    payload: UserLookupPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    result = await session.execute(
        select(User).where(User.external_id == payload.user_id)
    )
    user = result.scalars().first()
    data = {"username": user.username} if user and user.username else {}
    return {"success": True, "data": data}


@router.post("/instagram-user/follow-status")
async def instagram_follow_status(
    payload: UserLookupPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    result = await session.execute(
        select(User).where(User.external_id == payload.user_id)
    )
    user = result.scalars().first()
    data = {}
    if user and user.follow_status:
        parts: dict[str, str] = {}
        for item in user.follow_status.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
        if "is_follower" in parts:
            data["is_follower"] = parts["is_follower"] == "true"
        if "is_following" in parts:
            data["is_following"] = parts["is_following"] == "true"
    return {"success": True, "data": data}


@router.post("/instagram-user/follow-count")
async def instagram_follow_count(
    payload: UserLookupPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_service_key),
) -> dict:
    result = await session.execute(
        select(User).where(User.external_id == payload.user_id)
    )
    user = result.scalars().first()
    data = {"follower_count": user.follower_count} if user else {}
    return {"success": True, "data": data}
