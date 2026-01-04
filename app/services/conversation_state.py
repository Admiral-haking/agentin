from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_state import ConversationState
from app.services.product_taxonomy import infer_tags
from app.services.guardrails import (
    is_decline,
    is_goodbye,
    is_greeting,
    is_thanks,
    wants_address,
    wants_contact,
    wants_hours,
    wants_phone,
    wants_trust,
    wants_website,
)
from app.utils.time import utc_now

INTENT_STORE_INFO = "store_info"
INTENT_PRODUCT = "product_search"
INTENT_SUPPORT = "support"
INTENT_ORDER = "order"
INTENT_SMALLTALK = "smalltalk"

CATEGORY_SHOES = "shoes"
CATEGORY_APPAREL = "apparel"
CATEGORY_PERFUME = "perfume"
CATEGORY_COSMETICS = "cosmetics"
CATEGORY_ACCESSORIES = "accessories"
CATEGORY_UNKNOWN = "unknown"

SHOE_TAGS = {"کفش", "صندل و دمپایی", "مجلسی و طبی"}
APPAREL_TAGS = {"پوشاک", "لباس زیر", "شال و روسری", "کلاه و شال گردن"}
PERFUME_TAGS = {"عطر و ادکلن", "ادکلن", "بادی اسپلش", "اسپری"}
COSMETIC_TAGS = {"آرایشی و بهداشتی", "آرایشی", "بهداشتی"}
ACCESSORY_TAGS = {"اکسسوری", "کیف", "جوراب", "لوازم جانبی"}


def infer_intent(
    text: str,
    product_intent: bool,
    support_intent: bool,
    order_intent: bool,
) -> str:
    lowered = text.lower()
    if (
        wants_contact(lowered)
        or wants_website(lowered)
        or wants_address(lowered)
        or wants_hours(lowered)
        or wants_phone(lowered)
        or wants_trust(lowered)
    ):
        return INTENT_STORE_INFO
    if order_intent:
        return INTENT_ORDER
    if support_intent:
        return INTENT_SUPPORT
    if product_intent:
        return INTENT_PRODUCT
    if is_greeting(lowered) or is_thanks(lowered) or is_decline(lowered) or is_goodbye(lowered):
        return INTENT_SMALLTALK
    return INTENT_SMALLTALK


def infer_category(text: str | None) -> str:
    tags = infer_tags(text)
    categories = set(tags.categories)
    if categories & SHOE_TAGS:
        return CATEGORY_SHOES
    if categories & APPAREL_TAGS:
        return CATEGORY_APPAREL
    if categories & PERFUME_TAGS:
        return CATEGORY_PERFUME
    if categories & COSMETIC_TAGS:
        return CATEGORY_COSMETICS
    if categories & ACCESSORY_TAGS:
        return CATEGORY_ACCESSORIES
    return CATEGORY_UNKNOWN


async def get_or_create_state(
    session: AsyncSession, conversation_id: int
) -> ConversationState:
    result = await session.execute(
        select(ConversationState).where(
            ConversationState.conversation_id == conversation_id
        )
    )
    state = result.scalars().first()
    if state:
        return state
    state = ConversationState(conversation_id=conversation_id)
    session.add(state)
    await session.flush()
    return state


async def update_state(
    session: AsyncSession,
    conversation_id: int,
    current_intent: str,
    current_category: str,
    required_slots: list[str] | None,
    filled_slots: dict[str, Any] | None,
    last_user_question: str | None,
) -> ConversationState:
    state = await get_or_create_state(session, conversation_id)
    state.current_intent = current_intent
    state.current_category = current_category
    state.required_slots = required_slots
    state.filled_slots = filled_slots
    state.last_user_question = (last_user_question or "")[:500] or None
    state.updated_at = utc_now()
    await session.commit()
    return state


async def record_bot_action(
    session: AsyncSession,
    conversation_id: int,
    intent: str,
    answer: str | None,
) -> None:
    state = await get_or_create_state(session, conversation_id)
    state.last_bot_action = intent
    answers = state.last_bot_answers if isinstance(state.last_bot_answers, dict) else {}
    if answer:
        answers[intent] = answer[:800]
    state.last_bot_answers = answers
    state.updated_at = utc_now()
    await session.commit()


def build_state_payload(state: ConversationState | None) -> dict[str, Any] | None:
    if not state:
        return None
    return {
        "current_intent": state.current_intent,
        "current_category": state.current_category,
        "required_slots": state.required_slots,
        "filled_slots": state.filled_slots,
        "last_user_question": state.last_user_question,
        "last_bot_action": state.last_bot_action,
        "updated_at": state.updated_at.isoformat() if isinstance(state.updated_at, datetime) else None,
    }
