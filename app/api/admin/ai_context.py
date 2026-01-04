from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_session
from app.knowledge.store import get_store_knowledge_text
from app.models.bot_settings import BotSettings
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.admin.behavior import AIContextOut
from app.services.behavior_analyzer import build_behavior_context
from app.services.product_catalog import get_catalog_snapshot
from app.services.processor import build_response_log_summary, get_recent_response_logs
from app.services.prompts import load_prompt

router = APIRouter(prefix="/admin/ai", tags=["admin"])


@router.get("/context", response_model=AIContextOut)
async def get_ai_context(
    user_id: int | None = Query(default=None),
    external_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> AIContextOut:
    if user_id is None and not external_id:
        raise HTTPException(status_code=400, detail="user_id or external_id is required")

    if user_id is not None:
        user = await session.get(User, user_id)
    else:
        result = await session.execute(
            select(User).where(User.external_id == external_id)
        )
        user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await session.execute(
        select(BotSettings)
        .where(BotSettings.active.is_(True))
        .order_by(BotSettings.created_at.desc())
    )
    bot_settings = result.scalars().first()
    base_prompt = bot_settings.system_prompt if bot_settings else load_prompt("system.txt")
    store_knowledge = get_store_knowledge_text()

    catalog_snapshot = await get_catalog_snapshot(session)
    catalog_summary = catalog_snapshot.summary if catalog_snapshot else None

    behavior_context = None
    if isinstance(user.profile_json, dict):
        behavior_context = build_behavior_context(user.profile_json.get("behavior"))

    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    conversation = result.scalars().first()
    response_log_summary = None
    if conversation:
        logs = await get_recent_response_logs(session, conversation.id, 5)
        response_log_summary = build_response_log_summary(logs)

    compiled_parts = [
        part
        for part in [base_prompt, store_knowledge, catalog_summary, behavior_context, response_log_summary]
        if part
    ]
    compiled_context = "\n\n".join(compiled_parts).strip()

    return AIContextOut(
        user={"id": user.id, "external_id": user.external_id, "username": user.username},
        context=compiled_context,
        sections={
            "system_prompt": base_prompt,
            "store_knowledge": store_knowledge,
            "catalog": catalog_summary,
            "behavior": behavior_context,
            "recent_responses": response_log_summary,
        },
    )
