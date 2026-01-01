from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_session
from app.models.user import User
from app.schemas.send import Button, OutboundPlan, QuickReplyOption, TemplateElement
from app.services.processor import get_or_create_conversation, send_plan_and_store, within_window

router = APIRouter(prefix="/admin/directam", tags=["admin_directam"])


class DirectamSendPayload(BaseModel):
    receiver_id: str
    type: Literal[
        "text",
        "button",
        "quick_reply",
        "generic_template",
        "photo",
        "video",
        "audio",
    ]
    text: str | None = None
    image_url: str | None = None
    video_url: str | None = None
    audio_url: str | None = None
    buttons: list[Button] = Field(default_factory=list)
    quick_replies: list[QuickReplyOption] = Field(default_factory=list)
    elements: list[TemplateElement] = Field(default_factory=list)


class DirectamSendResponse(BaseModel):
    success: bool
    message: str
    message_id: str | None = None


class UserLookupPayload(BaseModel):
    user_id: str


@router.post("/send", response_model=DirectamSendResponse)
async def send_directam(
    payload: DirectamSendPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_current_admin),
) -> DirectamSendResponse:
    receiver_id = payload.receiver_id.strip()
    if not receiver_id:
        raise HTTPException(status_code=400, detail="receiver_id is required")

    result = await session.execute(
        select(User).where(User.external_id == receiver_id)
    )
    user = result.scalars().first()
    if not user:
        user = User(external_id=receiver_id)
        session.add(user)
        await session.flush()

    conversation = await get_or_create_conversation(session, user.id)
    if not await within_window(session, conversation.id):
        raise HTTPException(status_code=400, detail="24h window expired")

    plan = OutboundPlan.model_validate(
        payload.model_dump(exclude={"receiver_id"})
    )
    message_id = await send_plan_and_store(
        session, conversation.id, receiver_id, plan
    )
    if not message_id:
        raise HTTPException(status_code=502, detail="Send failed")

    return DirectamSendResponse(
        success=True,
        message="Message sent successfully",
        message_id=message_id,
    )


@router.post("/instagram-user/username")
async def instagram_username(
    payload: UserLookupPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_current_admin),
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
    _: None = Depends(get_current_admin),
) -> dict:
    result = await session.execute(
        select(User).where(User.external_id == payload.user_id)
    )
    user = result.scalars().first()
    data: dict = {}
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
    _: None = Depends(get_current_admin),
) -> dict:
    result = await session.execute(
        select(User).where(User.external_id == payload.user_id)
    )
    user = result.scalars().first()
    data = {"follower_count": user.follower_count} if user else {}
    return {"success": True, "data": data}
