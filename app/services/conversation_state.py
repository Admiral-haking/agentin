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
INTENT_PRODUCT_SELECTED = "product_selected"
INTENT_SUPPORT = "support"
INTENT_ORDER = "order_flow"
INTENT_UNKNOWN = "unknown"

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
        return INTENT_UNKNOWN
    return INTENT_UNKNOWN


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
    intent: str,
    category: str,
    slots_required: list[str] | None,
    slots_filled: dict[str, Any] | None,
    last_user_question: str | None,
    *,
    state: ConversationState | None = None,
    selected_product: dict[str, Any] | None = None,
    preserve_selected_product: bool = True,
    last_user_message_id: int | None = None,
    last_handler_used: str | None = None,
    loop_counter: int | None = None,
    increment_loop: bool = False,
    reset_loop: bool = False,
) -> ConversationState:
    state = state or await get_or_create_state(session, conversation_id)
    effective_selected = selected_product
    if preserve_selected_product and selected_product is None:
        effective_selected = state.selected_product
    if effective_selected and intent not in {INTENT_PRODUCT_SELECTED, INTENT_ORDER}:
        intent = INTENT_PRODUCT_SELECTED
    state.intent = intent
    state.category = category
    state.slots_required = slots_required
    state.slots_filled = slots_filled
    state.last_user_question = (last_user_question or "")[:500] or None
    if not preserve_selected_product or selected_product is not None:
        state.selected_product = selected_product
    if last_user_message_id is not None:
        state.last_user_message_id = last_user_message_id
    if last_handler_used is not None:
        state.last_handler_used = last_handler_used
    if reset_loop:
        state.loop_counter = 0
    elif increment_loop:
        state.loop_counter = (state.loop_counter or 0) + 1
    elif loop_counter is not None:
        state.loop_counter = loop_counter
    state.updated_at = utc_now()
    await session.commit()
    return state


async def record_bot_action(
    session: AsyncSession,
    conversation_id: int,
    intent: str,
    answer: str | None,
    *,
    handler_used: str | None = None,
) -> None:
    state = await get_or_create_state(session, conversation_id)
    state.last_bot_action = intent
    answers = (
        state.last_bot_answer_by_intent
        if isinstance(state.last_bot_answer_by_intent, dict)
        else {}
    )
    if answer:
        answers[intent] = answer[:800]
    state.last_bot_answer_by_intent = answers
    if handler_used is not None:
        state.last_handler_used = handler_used
    state.updated_at = utc_now()
    await session.commit()


def build_state_payload(state: ConversationState | None) -> dict[str, Any] | None:
    if not state:
        return None
    return {
        "intent": state.intent,
        "category": state.category,
        "current_intent": state.intent,
        "current_category": state.category,
        "slots_required": state.slots_required,
        "slots_filled": state.slots_filled,
        "required_slots": state.slots_required,
        "filled_slots": state.slots_filled,
        "selected_product": state.selected_product,
        "last_user_question": state.last_user_question,
        "last_user_message_id": state.last_user_message_id,
        "last_bot_action": state.last_bot_action,
        "last_bot_answer_by_intent": state.last_bot_answer_by_intent,
        "last_handler_used": state.last_handler_used,
        "loop_counter": state.loop_counter,
        "updated_at": state.updated_at.isoformat() if isinstance(state.updated_at, datetime) else None,
        "last_updated_at": state.updated_at.isoformat() if isinstance(state.updated_at, datetime) else None,
    }
