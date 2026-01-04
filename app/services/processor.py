from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import Integer, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import (
    BotSettings,
    Campaign,
    Conversation,
    Faq,
    Message,
    AppLog,
    Product,
    Usage,
    User,
)
from app.schemas.send import OutboundPlan
from app.schemas.webhook import NormalizedMessage
from app.knowledge.store import get_store_knowledge_text
from app.services.app_log_store import log_event
from app.services.guardrails import (
    build_decline_response,
    build_goodbye_response,
    build_rule_based_plan,
    build_thanks_response,
    fallback_for_message_type,
    fallback_llm_text,
    is_decline,
    is_goodbye,
    is_greeting,
    is_thanks,
    needs_product_details,
    plan_outbound,
    post_process,
    wants_product_intent,
    wants_address,
    wants_hours,
    wants_phone,
    wants_trust,
    wants_website,
)
from app.services.instagram_user_client import (
    InstagramUserClient,
    InstagramUserClientError,
)
from app.services.llm_clients import LLMError, generate_reply
from app.services.llm_router import choose_provider
from app.services.order_flow import handle_order_flow
from app.services.product_matcher import (
    match_products_with_scores,
    tokenize_query,
)
from app.services.product_catalog import get_catalog_snapshot
from app.services.behavior_analyzer import (
    analyze_user_behavior,
    build_behavior_context,
    build_behavior_profile,
    BehaviorMatch,
)
from app.services.product_presenter import build_product_plan, wants_product_list
from app.services.product_taxonomy import infer_tags
from app.services.prompts import load_prompt
from app.services.sender import Sender, SenderError
from app.services.user_profile import extract_preferences
from app.utils.time import parse_timestamp, utc_now

logger = structlog.get_logger(__name__)
SHOW_PRODUCTS_TOKEN = "[SHOW_PRODUCTS]"
REQUIRED_FIELD_LABELS = {
    "gender": "جنسیت (آقایون/خانم‌ها/بچگانه)",
    "size": "سایز",
    "style": "سبک (رسمی/اسپرت)",
    "budget": "بازه قیمت",
}


def _plan_to_text(plan: OutboundPlan) -> str:
    if plan.text:
        return plan.text
    if plan.type == "generic_template":
        lines = []
        for element in plan.elements:
            line = element.title
            if element.subtitle:
                line = f"{line} - {element.subtitle}"
            lines.append(line)
        if lines:
            return "\n".join(lines)
    return fallback_for_message_type("text")


def _split_show_products(text: str) -> tuple[bool, str]:
    if not text:
        return False, text
    lines = [line.rstrip() for line in text.splitlines()]
    show_products = any(line.strip() == SHOW_PRODUCTS_TOKEN for line in lines)
    if not show_products:
        return False, text.strip()
    cleaned = "\n".join(
        line for line in lines if line.strip() != SHOW_PRODUCTS_TOKEN
    ).strip()
    return True, cleaned


def _missing_required_fields(
    query_tags: Any,
    prefs: dict[str, Any] | None,
) -> tuple[list[str], dict[str, str]]:
    missing: list[str] = []
    known: dict[str, str] = {}
    prefs = prefs or {}

    gender = None
    if query_tags.genders:
        gender = "، ".join(query_tags.genders)
    elif isinstance(prefs.get("gender"), str):
        gender = prefs["gender"]
    if gender:
        known["gender"] = gender
    else:
        missing.append("gender")

    size = None
    if query_tags.sizes:
        size = "، ".join(query_tags.sizes)
    else:
        pref_sizes = prefs.get("sizes")
        if isinstance(pref_sizes, list) and pref_sizes:
            size = "، ".join(str(item) for item in pref_sizes)
    if size:
        known["size"] = size
    else:
        missing.append("size")

    style = None
    if query_tags.styles:
        style = "، ".join(query_tags.styles)
    if style:
        known["style"] = style
    else:
        missing.append("style")

    budget_min = prefs.get("budget_min") if isinstance(prefs.get("budget_min"), int) else None
    budget_max = prefs.get("budget_max") if isinstance(prefs.get("budget_max"), int) else None
    if budget_min is not None or budget_max is not None:
        if budget_min is not None and budget_max is not None:
            known["budget"] = f"{budget_min:,} تا {budget_max:,} تومان"
        elif budget_min is not None:
            known["budget"] = f"از {budget_min:,} تومان به بالا"
        else:
            known["budget"] = f"تا {budget_max:,} تومان"
    else:
        missing.append("budget")

    return missing, known


def _format_required_question(missing: list[str], known: dict[str, str]) -> str:
    known_parts = []
    for key, label in (("gender", "جنسیت"), ("size", "سایز"), ("style", "سبک"), ("budget", "بازه قیمت")):
        if key in known:
            known_parts.append(f"{label}: {known[key]}")
    prefix = ""
    if known_parts:
        prefix = f"{' | '.join(known_parts)}. "
    if not missing:
        return prefix + "برای معرفی دقیق‌تر، لطفاً اسم دقیق مدل یا عکسش رو بفرستید."
    labels = [REQUIRED_FIELD_LABELS[field] for field in missing]
    if len(labels) == 1:
        ask = labels[0]
    elif len(labels) == 2:
        ask = " و ".join(labels)
    else:
        ask = "، ".join(labels[:-1]) + " و " + labels[-1]
    return prefix + f"برای معرفی دقیق‌تر، لطفاً {ask} رو بگید."


def _contains_required_fields(text: str, missing: list[str]) -> bool:
    if not text:
        return False
    if not missing:
        lowered = text.lower()
        return any(keyword in lowered for keyword in ["مدل", "عکس", "تصویر"])
    lowered = text.lower()
    checks = {
        "gender": ["جنسیت", "آقا", "خانم", "مردانه", "زنانه", "بچگانه"],
        "size": ["سایز", "اندازه"],
        "style": ["رسمی", "اسپرت", "روزمره", "کلاسیک"],
        "budget": ["قیمت", "تومان", "بازه", "بودجه"],
    }
    return all(any(keyword in lowered for keyword in checks[field]) for field in missing)


def _is_low_signal(text: str | None) -> bool:
    if not text:
        return False
    tokens = [token for token in text.strip().split() if token]
    return len(tokens) <= 1


def _rank_products_by_prefs(
    products: list[Product],
    prefs: dict[str, Any] | None,
) -> list[Product]:
    if not products or not prefs:
        return products
    tokens: list[str] = []
    for key in ("categories", "gender", "colors"):
        value = prefs.get(key)
        if isinstance(value, list):
            tokens.extend([item for item in value if isinstance(item, str)])
        elif isinstance(value, str):
            tokens.append(value)
    tokens = [token.strip().lower() for token in tokens if token and token.strip()]
    budget_min = prefs.get("budget_min") if isinstance(prefs.get("budget_min"), int) else None
    budget_max = prefs.get("budget_max") if isinstance(prefs.get("budget_max"), int) else None
    if not tokens and budget_min is None and budget_max is None:
        return products
    scored: list[tuple[int, datetime, Product]] = []
    for product in products:
        haystack = " ".join(
            part
            for part in [
                product.slug,
                product.title,
                product.description,
                product.product_id,
            ]
            if part
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if product.price is not None and (budget_min is not None or budget_max is not None):
            if (budget_min is None or product.price >= budget_min) and (
                budget_max is None or product.price <= budget_max
            ):
                score += 1
        scored.append((score, product.updated_at or datetime.min, product))
    max_score = max(item[0] for item in scored) if scored else 0
    if max_score <= 0:
        return products
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored]

SALES_KEYWORDS = {
    "price",
    "pricing",
    "buy",
    "order",
    "purchase",
    "قیمت",
    "خرید",
    "سفارش",
    "پرداخت",
}
SUPPORT_KEYWORDS = {
    "problem",
    "issue",
    "error",
    "refund",
    "complaint",
    "support",
    "مشکل",
    "خرابی",
    "خطا",
    "شکایت",
    "مرجوع",
    "پشتیبانی",
}

FAQ_MATCH_MIN_LEN = 4


def normalize_webhook(payload: dict[str, Any]) -> NormalizedMessage:
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)

    sender_id = payload.get("sender")
    receiver_id = payload.get("receiver")
    message_type = payload.get("message_type")
    if not sender_id or not receiver_id or not message_type:
        raise ValueError("Missing sender, receiver, or message_type")

    raw_type = str(message_type).lower().strip()
    if raw_type in {"image", "photo", "picture", "video", "media"}:
        message_type = "media"
    elif raw_type in {"audio", "voice"}:
        message_type = "audio"
    elif raw_type in {"text", "quick_reply", "postback", "button", "interactive"}:
        message_type = "text"
    elif raw_type == "read":
        message_type = "read"
    else:
        raise ValueError("Unsupported message_type")

    text = payload.get("text")
    if not text:
        payload_value = payload.get("payload")
        if isinstance(payload_value, str):
            text = payload_value
        else:
            quick_reply = payload.get("quick_reply")
            if isinstance(quick_reply, dict):
                text = quick_reply.get("payload") or quick_reply.get("title")
            postback = payload.get("postback")
            if not text and isinstance(postback, dict):
                text = postback.get("payload") or postback.get("title")
            message_value = payload.get("message")
            if not text and isinstance(message_value, str):
                text = message_value
    timestamp = parse_timestamp(payload.get("timestamp"))

    is_admin = payload.get("is_admin")
    if is_admin is None:
        is_admin = payload.get("admin_is")
    is_admin = _coerce_bool(is_admin) if is_admin is not None else False

    media_url = None
    audio_url = None
    media = payload.get("media")
    if isinstance(media, dict):
        media_url_value = media.get("url")
        media_type = media.get("type")
        media_type = str(media_type).lower().strip() if media_type is not None else None
        if media_url_value is not None:
            if message_type == "audio" or media_type == "audio":
                audio_url = str(media_url_value)
            else:
                media_url = str(media_url_value)

    read_message_id = None
    if message_type == "read":
        read = payload.get("read")
        if isinstance(read, dict):
            read_message_id = read.get("message_id")

    return NormalizedMessage(
        sender_id=str(sender_id),
        receiver_id=str(receiver_id),
        message_type=message_type,
        text=str(text) if text is not None else None,
        media_url=media_url,
        audio_url=audio_url,
        is_admin=is_admin,
        read_message_id=str(read_message_id) if read_message_id is not None else None,
        timestamp=timestamp,
        username=None,
        follow_status=None,
        follower_count=None,
        raw_payload=payload,
    )


def normalize_payload(payload: dict[str, Any]) -> NormalizedMessage:
    return normalize_webhook(payload)


async def enrich_user_profile(message: NormalizedMessage) -> None:
    if (
        message.username
        and message.follow_status
        and message.follower_count is not None
    ):
        return
    if not settings.DIRECTAM_BASE_URL or not settings.SERVICE_API_KEY:
        return

    client = InstagramUserClient()
    try:
        if not message.username:
            message.username = await client.get_username(message.sender_id)
        if not message.follow_status:
            message.follow_status = await client.get_follow_status(message.sender_id)
        if message.follower_count is None:
            message.follower_count = await client.get_follow_count(message.sender_id)
    except InstagramUserClientError as exc:
        logger.warning("user_enrich_failed", error=str(exc))


async def handle_webhook(payload: dict[str, Any]) -> None:
    try:
        normalized = normalize_webhook(payload)
    except ValueError as exc:
        logger.warning("webhook_invalid", error=str(exc))
        return

    if not normalized.is_admin and normalized.message_type != "read":
        await enrich_user_profile(normalized)

    logger.info(
        "webhook_received",
        sender_id=normalized.sender_id,
        message_type=normalized.message_type,
        is_admin=normalized.is_admin,
        has_text=bool(normalized.text),
    )

    async with AsyncSessionLocal() as session:
        try:
            user = await upsert_user(session, normalized)
            conversation = await get_or_create_conversation(session, user.id)
            role = "admin" if normalized.is_admin else "user"

            await save_message(session, conversation.id, normalized, role)
            if role == "user" and normalized.message_type != "read":
                conversation.last_user_message_at = normalized.timestamp or utc_now()
            await log_event(
                session,
                level="info",
                event_type="webhook_received",
                data={
                    "sender_id": normalized.sender_id,
                    "message_type": normalized.message_type,
                    "is_admin": normalized.is_admin,
                },
                commit=False,
            )
            await session.commit()

            if normalized.is_admin:
                logger.info("admin_ignored", sender_id=normalized.sender_id)
                return
            if normalized.message_type == "read":
                logger.info("read_ignored", sender_id=normalized.sender_id)
                return

            bot_settings = await get_active_bot_settings(session)
            max_history = (
                bot_settings.max_history_messages
                if bot_settings and bot_settings.max_history_messages
                else settings.MAX_HISTORY_MESSAGES
            )
            history_limit = max_history
            if settings.LLM_MAX_USER_TURNS > 0:
                history_limit = min(
                    history_limit, settings.LLM_MAX_USER_TURNS * 2 + 6
                )
            history_limit = max(history_limit, 1)
            history = await get_recent_history(
                session, conversation.id, history_limit
            )
            is_first_message = (
                sum(1 for msg in history if msg.role == "user" and msg.type != "read")
                <= 1
            )
            catalog_snapshot = await get_catalog_snapshot(session)
            catalog_summary = catalog_snapshot.summary if catalog_snapshot else None
            behavior_match: BehaviorMatch | None = None
            behavior_summary: dict[str, int] = {}
            behavior_recent: list[dict[str, Any]] = []
            behavior_meta: dict[str, Any] | None = None
            behavior_context: str | None = None
            def _merge_meta(extra: dict[str, Any] | None) -> dict[str, Any] | None:
                if behavior_meta is None and not extra:
                    return None
                merged: dict[str, Any] = {}
                if behavior_meta:
                    merged.update(behavior_meta)
                if extra:
                    merged.update(extra)
                return merged

            llm_first_all = settings.LLM_FIRST_ALL
            lowered = (normalized.text or "").strip().lower()
            if normalized.text:
                behavior_match, behavior_summary, behavior_recent = await analyze_user_behavior(
                    session,
                    user.id,
                    normalized.text,
                    settings.BEHAVIOR_HISTORY_LIMIT,
                )
                profile = user.profile_json if isinstance(user.profile_json, dict) else {}
                behavior_profile = build_behavior_profile(
                    behavior_match,
                    behavior_summary,
                    behavior_recent,
                    normalized.text,
                )
                if behavior_profile:
                    profile["behavior"] = behavior_profile
                    user.profile_json = profile
                    await session.commit()
                behavior_context = build_behavior_context(profile.get("behavior"))
                pattern_payload = {
                    "pattern": "unknown",
                    "confidence": 0.0,
                    "reason": "no_match",
                    "keywords": [],
                    "tags": [],
                }
                if behavior_match:
                    behavior_meta = {
                        "behavior_pattern": behavior_match.pattern,
                        "behavior_confidence": behavior_match.confidence,
                    }
                    pattern_payload = {
                        "pattern": behavior_match.pattern,
                        "confidence": behavior_match.confidence,
                        "reason": behavior_match.reason,
                        "keywords": list(behavior_match.keywords),
                        "tags": list(behavior_match.tags),
                    }
                await log_event(
                    session,
                    level="info",
                    event_type="pattern_detected",
                    data={
                        "user_id": user.id,
                        "conversation_id": conversation.id,
                        **pattern_payload,
                    },
                    commit=False,
                )
                await session.commit()

                store_intent = (
                    is_greeting(lowered)
                    or wants_website(lowered)
                    or wants_address(lowered)
                    or wants_hours(lowered)
                    or wants_phone(lowered)
                    or wants_trust(lowered)
                )
                if not llm_first_all:
                    if is_thanks(lowered):
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            build_thanks_response(),
                            meta=_merge_meta({"source": "guardrails", "intent": "thanks"}),
                        )
                        return
                    if is_decline(lowered):
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            build_decline_response(),
                            meta=_merge_meta({"source": "guardrails", "intent": "decline"}),
                        )
                        return
                    if is_goodbye(lowered):
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            build_goodbye_response(),
                            meta=_merge_meta({"source": "guardrails", "intent": "goodbye"}),
                        )
                        return
                    if store_intent:
                        store_topic = None
                        if wants_hours(lowered):
                            store_topic = "hours"
                        elif wants_address(lowered):
                            store_topic = "address"
                        elif wants_phone(lowered):
                            store_topic = "phone"
                        elif wants_website(lowered):
                            store_topic = "website"
                        elif wants_trust(lowered):
                            store_topic = "trust"
                        rule_plan = build_rule_based_plan(
                            normalized.message_type,
                            normalized.text,
                            is_first_message,
                        )
                        if rule_plan:
                            await send_plan_and_store(
                                session,
                                conversation.id,
                                normalized.sender_id,
                                rule_plan,
                                meta=_merge_meta({
                                    "source": "guardrails",
                                    "intent": "store_info",
                                    "store_topic": store_topic,
                                }),
                            )
                            return

            if behavior_context is None and isinstance(user.profile_json, dict):
                behavior_context = build_behavior_context(user.profile_json.get("behavior"))

            if normalized.text:
                pref_updates = extract_preferences(normalized.text)
                if pref_updates:
                    profile = user.profile_json or {}
                    prefs = profile.get("prefs", {}) if isinstance(profile, dict) else {}
                    changed = False
                    for key, value in pref_updates.items():
                        if value is None:
                            continue
                        if isinstance(value, list):
                            existing = prefs.get(key, [])
                            merged = list(dict.fromkeys((existing or []) + value))
                            if merged != existing:
                                prefs[key] = merged
                                changed = True
                        else:
                            if prefs.get(key) != value:
                                prefs[key] = value
                                changed = True
                    if changed:
                        profile["prefs"] = prefs
                        user.profile_json = profile
                        await session.commit()

            order_plan = await handle_order_flow(session, user, normalized.text)
            order_hint_text = None
            if order_plan:
                order_hint_text = _plan_to_text(order_plan)
                if not llm_first_all:
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        order_plan,
                        meta=_merge_meta({"source": "order_flow", "intent": "order_flow"}),
                    )
                    return

            tokens = tokenize_query(normalized.text)
            query_tags = infer_tags(normalized.text)
            wants_products = wants_product_list(normalized.text)
            needs_details = needs_product_details(lowered)
            store_intent = (
                is_greeting(lowered)
                or wants_website(lowered)
                or wants_address(lowered)
                or wants_hours(lowered)
                or wants_phone(lowered)
                or wants_trust(lowered)
            )
            product_intent = wants_product_intent(lowered)
            if (
                not store_intent
                and (
                    query_tags.categories
                    or query_tags.genders
                    or query_tags.materials
                    or query_tags.styles
                )
            ):
                product_intent = True

            should_match_products = bool(normalized.text) and (
                product_intent
                or wants_products
                or needs_details
                or query_tags.categories
                or query_tags.genders
                or query_tags.materials
                or query_tags.styles
                or query_tags.colors
                or query_tags.sizes
            )
            matches_for_context = []
            if should_match_products:
                matches_for_context = await match_products_with_scores(
                    session,
                    normalized.text,
                    limit=max(
                        settings.LLM_PRODUCT_CONTEXT_LIMIT,
                        settings.PRODUCT_MATCH_LIMIT,
                    ),
                )
            matched_products_for_llm = [match.product for match in matches_for_context]
            matched_products = matched_products_for_llm[: settings.PRODUCT_MATCH_LIMIT]

            is_plain_list_request = (
                wants_products
                and len(tokens) <= 1
                and not (
                    query_tags.categories
                    or query_tags.genders
                    or query_tags.materials
                    or query_tags.styles
                    or query_tags.colors
                    or query_tags.sizes
                )
            )
            if wants_products and not matched_products_for_llm and is_plain_list_request:
                result = await session.execute(
                    select(Product)
                    .order_by(Product.updated_at.desc())
                    .limit(settings.LLM_PRODUCT_CONTEXT_LIMIT)
                )
                matched_products_for_llm = list(result.scalars().all())
                matched_products = matched_products_for_llm[: settings.PRODUCT_MATCH_LIMIT]

            prefs = None
            if isinstance(user.profile_json, dict):
                prefs = user.profile_json.get("prefs")
            matched_products_for_llm = _rank_products_by_prefs(matched_products_for_llm, prefs)
            matched_products = _rank_products_by_prefs(matched_products, prefs)
            matched_product_ids = [product.id for product in matched_products]
            matched_product_slugs = [product.slug for product in matched_products if product.slug]

            confidence_ok = True
            low_confidence = False
            if product_intent or needs_details or wants_products:
                top_match = matches_for_context[0] if matches_for_context else None
                if not top_match:
                    confidence_ok = False
                else:
                    if tokens:
                        required_score = max(2, len(tokens))
                        if len(tokens) >= 3:
                            required_score = max(3, len(tokens))
                        confidence_ok = top_match.score >= required_score
                    else:
                        confidence_ok = top_match.score >= 2
                low_confidence = not confidence_ok

            required_fields: list[str] = []
            required_known: dict[str, str] = {}
            required_question_text: str | None = None
            if settings.LLM_REQUIRE_FIELDS_ON_LOW_CONF and low_confidence:
                required_fields, required_known = _missing_required_fields(query_tags, prefs)
                required_question_text = _format_required_question(required_fields, required_known)

            if not llm_first_all:
                if matched_products and (product_intent or needs_details or wants_products) and low_confidence:
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        required_question_text
                        or "برای معرفی دقیق‌تر، لطفاً جنسیت، سایز، سبک (رسمی/اسپرت) و بازه قیمت رو بگید.",
                        meta=_merge_meta({
                            "source": "product_match",
                            "intent": "need_details",
                            "product_ids": matched_product_ids,
                            "product_slugs": matched_product_slugs,
                            "confidence_ok": False,
                        }),
                    )
                    return

                if matched_products and not store_intent and (confidence_ok or is_plain_list_request):
                    product_plan = build_product_plan(normalized.text, matched_products)
                    if product_plan:
                        await send_plan_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            product_plan,
                            meta=_merge_meta({
                                "source": "product_match",
                                "intent": "product_suggest",
                                "product_ids": matched_product_ids,
                                "product_slugs": matched_product_slugs,
                                "confidence_ok": confidence_ok,
                            }),
                        )
                        return
                if product_intent and not matched_products:
                    await send_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        "برای معرفی دقیق‌تر، لطفاً جنسیت، سایز، سبک (رسمی/اسپرت) و بازه قیمت رو بگید؛ اگر مدل خاصی دارید اسم یا عکسش رو بفرستید.",
                        meta=_merge_meta({"source": "product_match", "intent": "no_match"}),
                    )
                    return

                if normalized.text and _is_low_signal(normalized.text):
                    if not (
                        is_greeting(lowered)
                        or wants_products
                        or needs_details
                        or wants_website(lowered)
                        or wants_address(lowered)
                        or wants_hours(lowered)
                        or wants_phone(lowered)
                        or wants_trust(lowered)
                    ):
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            fallback_for_message_type("text"),
                            meta=_merge_meta({"source": "guardrails", "intent": "low_signal"}),
                        )
                        return

                rule_plan = build_rule_based_plan(
                    normalized.message_type,
                    normalized.text,
                    is_first_message,
                )
                if rule_plan:
                    await send_plan_and_store(
                        session,
                        conversation.id,
                        normalized.sender_id,
                        rule_plan,
                        meta=_merge_meta({"source": "guardrails", "intent": "rule_based"}),
                    )
                    return

                faqs = await get_verified_faqs(session)
                if normalized.text and faqs:
                    faq_answer = match_faq(normalized.text, faqs)
                    if faq_answer:
                        await send_and_store(
                            session,
                            conversation.id,
                            normalized.sender_id,
                            faq_answer,
                            meta=_merge_meta({"source": "faq", "intent": "faq_match"}),
                        )
                        return
            else:
                faqs = await get_verified_faqs(session)

            campaigns = await get_active_campaigns(session)
            llm_products = matched_products_for_llm if should_match_products else []
            response_logs = await get_recent_response_logs(
                session,
                conversation.id,
                settings.RESPONSE_LOG_CONTEXT_LIMIT,
            )
            response_log_summary = build_response_log_summary(response_logs)
            system_notes: list[str] = []
            if order_hint_text:
                system_notes.append(
                    "[ORDER_FLOW]\n"
                    f"کاربر در جریان ثبت سفارش است. لطفاً همین پیام را ارسال کن:\n{order_hint_text}\n"
                    "تا زمانی که این مرحله کامل نشده، پیشنهاد محصول نده."
                )
            if low_confidence and required_question_text:
                system_notes.append(
                    "[NEED_DETAILS]\n"
                    f"اعتماد پایین است. قبل از پیشنهاد محصول این سؤال را بپرس:\n{required_question_text}\n"
                    "تا جزئیات کامل نشده، محصول پیشنهاد نده."
                )
            allow_product_cards = bool(
                matched_products
                and not low_confidence
                and not order_hint_text
                and (product_intent or wants_products or needs_details)
            )
            llm_messages = build_llm_messages(
                history,
                bot_settings,
                normalized,
                user,
                llm_products,
                catalog_summary=catalog_summary,
                response_log_summary=response_log_summary,
                behavior_context=behavior_context,
                system_notes=system_notes,
                allow_product_cards=allow_product_cards,
            )
            llm_messages = inject_campaigns_and_faqs(llm_messages, campaigns, faqs)

            provider = choose_provider(
                normalized, bot_settings.ai_mode if bot_settings else None
            )
            logger.info("provider_selected", provider=provider)
            await log_event(
                session,
                level="info",
                event_type="provider_selected",
                data={"provider": provider, "sender_id": normalized.sender_id},
                commit=False,
            )
            start_time = time.monotonic()
            provider_used = None

            try:
                reply_text, usage, provider_used = await generate_with_fallback(
                    provider, llm_messages
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "llm_latency_ms",
                    provider=provider_used,
                    latency_ms=latency_ms,
                )
                await log_event(
                    session,
                    level="info",
                    event_type="llm_latency",
                    data={"provider": provider_used, "latency_ms": latency_ms},
                    commit=False,
                )
                max_chars = (
                    bot_settings.max_output_chars
                    if bot_settings and bot_settings.max_output_chars
                    else settings.MAX_RESPONSE_CHARS
                )
                fallback_text = (
                    bot_settings.fallback_text
                    if bot_settings and bot_settings.fallback_text
                    else fallback_llm_text()
                )
                reply_text = post_process(reply_text, max_chars=max_chars, fallback_text=fallback_text)
                await record_usage(session, usage, provider_used)
            except LLMError as exc:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(
                    "errors",
                    stage="llm",
                    error=str(exc),
                    latency_ms=latency_ms,
                )
                await log_event(
                    session,
                    level="error",
                    event_type="llm_error",
                    message=str(exc),
                    data={"latency_ms": latency_ms},
                )
                reply_text = (
                    bot_settings.fallback_text
                    if bot_settings and bot_settings.fallback_text
                    else fallback_llm_text()
                )

            show_products = False
            if llm_first_all and allow_product_cards:
                show_products, reply_text = _split_show_products(reply_text)

            if order_hint_text:
                reply_text = order_hint_text
                show_products = False
            elif required_question_text and not _contains_required_fields(reply_text, required_fields):
                reply_text = required_question_text
                show_products = False

            product_plan = None
            if show_products and matched_products:
                product_plan = build_product_plan(normalized.text, matched_products)

            if reply_text:
                await send_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    reply_text,
                    meta=_merge_meta({
                        "source": "llm",
                        "intent": "llm",
                        "provider": provider_used,
                        "product_context_count": len(llm_products),
                        "product_ids": matched_product_ids,
                        "product_slugs": matched_product_slugs,
                        "catalog_used": bool(catalog_summary),
                        "response_logs_used": bool(response_log_summary),
                        "llm_first": llm_first_all,
                        "confidence_ok": confidence_ok,
                        "low_confidence": low_confidence,
                        "required_fields": required_fields,
                        "order_flow": bool(order_hint_text),
                        "show_products_token": show_products,
                    }),
                )

            if product_plan:
                await send_plan_and_store(
                    session,
                    conversation.id,
                    normalized.sender_id,
                    product_plan,
                    meta=_merge_meta({
                        "source": "product_match",
                        "intent": "product_suggest",
                        "product_ids": matched_product_ids,
                        "product_slugs": matched_product_slugs,
                        "confidence_ok": confidence_ok,
                        "llm_first": llm_first_all,
                    }),
                )
        except Exception as exc:
            logger.error("errors", stage="processor", error=str(exc))
            await session.rollback()


async def upsert_user(session: AsyncSession, message: NormalizedMessage) -> User:
    result = await session.execute(
        select(User).where(User.external_id == message.sender_id)
    )
    user = result.scalars().first()
    if user:
        if message.username:
            user.username = message.username
        if message.follow_status:
            user.follow_status = message.follow_status
        if message.follower_count is not None:
            user.follower_count = message.follower_count
        return user

    user = User(
        external_id=message.sender_id,
        username=message.username,
        follow_status=message.follow_status,
        follower_count=message.follower_count,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_conversation(session: AsyncSession, user_id: int) -> Conversation:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.status == "open")
        .order_by(Conversation.created_at.desc())
    )
    conversation = result.scalars().first()
    if conversation:
        return conversation

    conversation = Conversation(user_id=user_id, status="open")
    session.add(conversation)
    await session.flush()
    return conversation


async def save_message(
    session: AsyncSession,
    conversation_id: int,
    message: NormalizedMessage,
    role: str,
) -> Message:
    content_text = message.text
    if message.message_type == "read" and message.read_message_id:
        content_text = message.read_message_id
    record = Message(
        conversation_id=conversation_id,
        role=role,
        type=message.message_type,
        content_text=content_text,
        media_url=message.media_url or message.audio_url,
        payload_json=message.raw_payload,
    )
    session.add(record)
    await session.flush()
    return record


async def get_active_bot_settings(session: AsyncSession) -> BotSettings | None:
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


async def get_recent_history(
    session: AsyncSession, conversation_id: int, limit: int
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_recent_response_logs(
    session: AsyncSession,
    conversation_id: int,
    limit: int,
) -> list[AppLog]:
    if limit <= 0:
        return []
    result = await session.execute(
        select(AppLog)
        .where(AppLog.event_type == "assistant_response")
        .where(cast(AppLog.data["conversation_id"].astext, Integer) == conversation_id)
        .order_by(AppLog.created_at.desc())
        .limit(limit)
    )
    logs = list(result.scalars().all())
    logs.reverse()
    return logs


def build_response_log_summary(logs: list[AppLog]) -> str | None:
    if not logs:
        return None
    lines: list[str] = []
    for log in logs:
        message = (log.message or "").strip()
        if not message:
            continue
        data = log.data or {}
        source = data.get("source", "reply")
        intent = data.get("intent")
        tag = source if not intent else f"{source}/{intent}"
        snippet = " ".join(message.split())
        if len(snippet) > settings.LLM_MESSAGE_MAX_CHARS:
            snippet = snippet[: settings.LLM_MESSAGE_MAX_CHARS].rstrip() + "..."
        lines.append(f"- [{tag}] {snippet}")
    if not lines:
        return None
    summary = "[RECENT_RESPONSES]\n" + "\n".join(lines)
    if len(summary) > settings.LLM_MESSAGE_MAX_CHARS:
        summary = summary[: settings.LLM_MESSAGE_MAX_CHARS].rstrip() + "..."
    return summary


def _trim_history_for_llm(
    history: list[Message], max_user_turns: int
) -> list[Message]:
    if max_user_turns <= 0:
        return history
    trimmed: list[Message] = []
    user_turns = 0
    for msg in reversed(history):
        trimmed.append(msg)
        if msg.role == "user" and msg.type != "read":
            user_turns += 1
            if user_turns >= max_user_turns:
                break
    trimmed.reverse()
    return trimmed


async def get_verified_faqs(session: AsyncSession, limit: int = 30) -> list[Faq]:
    result = await session.execute(
        select(Faq)
        .where(Faq.verified.is_(True))
        .order_by(Faq.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_active_campaigns(session: AsyncSession, limit: int = 5) -> list[Campaign]:
    now = utc_now()
    query = (
        select(Campaign)
        .where(Campaign.active.is_(True))
        .where((Campaign.start_at.is_(None)) | (Campaign.start_at <= now))
        .where((Campaign.end_at.is_(None)) | (Campaign.end_at >= now))
        .order_by(Campaign.priority.desc(), Campaign.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


def match_faq(text: str, faqs: list[Faq]) -> str | None:
    normalized = text.strip().lower()
    for faq in faqs:
        if faq.question and faq.question.strip().lower() in normalized:
            return faq.answer
        if faq.tags:
            for tag in faq.tags:
                if tag and tag.strip().lower() in normalized and len(tag) >= FAQ_MATCH_MIN_LEN:
                    return faq.answer
    return None


def inject_campaigns_and_faqs(
    messages: list[dict[str, str]],
    campaigns: list[Campaign],
    faqs: list[Faq],
) -> list[dict[str, str]]:
    additions: list[str] = []
    if campaigns:
        lines = []
        for campaign in campaigns:
            parts = [campaign.title, campaign.body]
            if campaign.discount_code:
                parts.append(f"کد تخفیف: {campaign.discount_code}")
            if campaign.link:
                parts.append(f"لینک: {campaign.link}")
            lines.append(" | ".join(part for part in parts if part))
        additions.append("کمپین‌های فعال:\n" + "\n".join(f"- {line}" for line in lines))
    if faqs:
        faq_lines = [
            f"Q: {faq.question}\nA: {faq.answer}" for faq in faqs if faq.question and faq.answer
        ]
        if faq_lines:
            additions.append("FAQ تاییدشده:\n" + "\n".join(faq_lines))
    if not additions:
        return messages
    return messages + [{"role": "system", "content": "\n\n".join(additions)}]


def build_llm_messages(
    history: list[Message],
    bot_settings: BotSettings | None,
    message: NormalizedMessage,
    user: User,
    products: list[Product] | None = None,
    catalog_summary: str | None = None,
    response_log_summary: str | None = None,
    behavior_context: str | None = None,
    system_notes: list[str] | None = None,
    allow_product_cards: bool = False,
) -> list[dict[str, str]]:
    history = _trim_history_for_llm(history, settings.LLM_MAX_USER_TURNS)
    base_prompt = bot_settings.system_prompt if bot_settings else load_prompt("system.txt")
    store_knowledge = get_store_knowledge_text()
    prompt_parts = [base_prompt, store_knowledge]
    if catalog_summary:
        prompt_parts.append(catalog_summary)
    if behavior_context:
        prompt_parts.append(behavior_context)
    if system_notes:
        prompt_parts.extend(note for note in system_notes if note)

    if message.text:
        lowered = message.text.lower()
        if any(keyword in lowered for keyword in SALES_KEYWORDS):
            prompt_parts.append(load_prompt("sales.txt"))
        if any(keyword in lowered for keyword in SUPPORT_KEYWORDS):
            prompt_parts.append(load_prompt("support.txt"))

    profile_bits = []
    if user.username:
        profile_bits.append(f"username={user.username}")
    if user.follow_status:
        profile_bits.append(f"follow_status={user.follow_status}")
    if user.follower_count is not None:
        profile_bits.append(f"follower_count={user.follower_count}")

    system_prompt = "\n\n".join(part for part in prompt_parts if part).strip()
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if response_log_summary:
        messages.append({"role": "system", "content": response_log_summary})
    if profile_bits:
        messages.append(
            {
                "role": "system",
                "content": f"User profile: {', '.join(profile_bits)}",
            }
        )
    if user.profile_json and isinstance(user.profile_json, dict):
        prefs = user.profile_json.get("prefs")
        if isinstance(prefs, dict) and prefs:
            pref_bits = []
            for key in ("categories", "gender", "sizes", "colors", "budget_min", "budget_max"):
                value = prefs.get(key)
                if value is None:
                    continue
                if isinstance(value, list):
                    if value:
                        pref_bits.append(f"{key}={', '.join(str(item) for item in value)}")
                else:
                    pref_bits.append(f"{key}={value}")
            if pref_bits:
                messages.append(
                    {
                        "role": "system",
                        "content": f"User preferences: {', '.join(pref_bits)}",
                    }
                )

    if products:
        product_lines: list[str] = []
        for product in products:
            title = product.title or product.slug or "بدون عنوان"
            price = str(product.price) if product.price is not None else "نامشخص"
            old_price = (
                str(product.old_price) if product.old_price is not None else None
            )
            availability = (
                product.availability.value
                if hasattr(product.availability, "value")
                else str(product.availability)
            )
            product_tags = infer_tags(
                " ".join(
                    part
                    for part in [
                        product.slug,
                        product.title,
                        product.description,
                        product.product_id,
                    ]
                    if part
                )
            )
            parts = [title, f"قیمت: {price}"]
            if old_price:
                parts.append(f"قبل: {old_price}")
            parts.append(f"موجودی: {availability}")
            if product.product_id:
                parts.append(f"مدل: {product.product_id}")
            if product_tags.categories:
                parts.append(f"دسته: {', '.join(product_tags.categories)}")
            if product_tags.genders:
                parts.append(f"جنسیت: {', '.join(product_tags.genders)}")
            if product_tags.materials:
                parts.append(f"جنس: {', '.join(product_tags.materials)}")
            if product_tags.styles:
                parts.append(f"سبک: {', '.join(product_tags.styles)}")
            if product_tags.colors:
                parts.append(f"رنگ: {', '.join(product_tags.colors[:3])}")
            if product.page_url:
                parts.append(f"لینک: {product.page_url}")
            product_lines.append(" | ".join(parts))
        product_context = (
            "[PRODUCTS]\n"
            + "\n".join(f"- {line}" for line in product_lines)
            + "\n"
            "Rules:\n"
            "- فقط از قیمت‌های بالا استفاده کن و قیمت جدید نساز.\n"
            "- اگر قیمت نامشخص بود، همین را اعلام کن و از کاربر جزئیات بپرس."
        )
        if allow_product_cards:
            product_context += (
                "\n- اگر می‌خواهی کارت محصول نمایش داده شود، دقیقاً یک خط جدا شامل "
                f"{SHOW_PRODUCTS_TOKEN} بنویس."
            )
        messages.append({"role": "system", "content": product_context})

    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        if item.type == "read":
            continue
        content = item.content_text
        if not content:
            content = f"[{item.type.upper()}]"
        messages.append({"role": item.role, "content": content})

    return messages


async def generate_with_fallback(
    primary_provider: str, messages: list[dict[str, str]]
) -> tuple[str, dict, str]:
    providers = [primary_provider]
    fallback = "deepseek" if primary_provider == "openai" else "openai"
    if fallback not in providers:
        providers.append(fallback)

    last_error: Exception | None = None
    for provider in providers:
        try:
            reply_text, usage = await generate_reply(provider, messages)
            return reply_text, usage, provider
        except LLMError as exc:
            last_error = exc
            logger.warning("provider_failed", provider=provider)

    raise LLMError(f"All providers failed: {last_error}")


async def record_usage(session: AsyncSession, usage: dict | None, provider: str) -> None:
    tokens_in = usage.get("prompt_tokens") if usage else None
    tokens_out = usage.get("completion_tokens") if usage else None
    record = Usage(
        date=utc_now().date(),
        provider=provider,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=None,
    )
    session.add(record)
    await session.commit()


async def within_window(session: AsyncSession, conversation_id: int) -> bool:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation or not conversation.last_user_message_at:
        return False
    delta = utc_now() - conversation.last_user_message_at
    return delta.total_seconds() <= settings.WINDOW_HOURS * 3600


async def send_and_store(
    session: AsyncSession,
    conversation_id: int,
    receiver_id: str,
    text: str,
    meta: dict | None = None,
) -> None:
    plan = plan_outbound(text)
    await send_plan_and_store(session, conversation_id, receiver_id, plan, meta=meta)


async def send_plan_and_store(
    session: AsyncSession,
    conversation_id: int,
    receiver_id: str,
    plan: OutboundPlan,
    meta: dict | None = None,
) -> str | None:
    def _plan_to_text(value: OutboundPlan) -> str:
        if value.text:
            return value.text
        if value.type == "generic_template":
            lines = []
            for element in value.elements:
                line = element.title
                if element.subtitle:
                    line = f"{line} - {element.subtitle}"
                lines.append(line)
            if lines:
                return "\n".join(lines)
        return fallback_for_message_type("text")

    if not await within_window(session, conversation_id):
        logger.info(
            "window_expired",
            receiver_id=receiver_id,
            conversation_id=conversation_id,
        )
        await log_event(
            session,
            level="info",
            event_type="window_expired",
            message="24h window expired",
            data={"receiver_id": receiver_id, "conversation_id": conversation_id},
        )
        return None

    if plan.type in {"text", "button", "quick_reply"} and not plan.text:
        plan.text = fallback_for_message_type("text")
    if plan.type == "generic_template" and not plan.elements:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.type == "photo" and not plan.image_url:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.type == "video" and not plan.video_url:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.type == "audio" and not plan.audio_url:
        plan.type = "text"
        plan.text = fallback_for_message_type("text")
    if plan.text:
        plan.text = plan.text[: settings.MAX_RESPONSE_CHARS].strip()

    if plan.type == "button":
        plan.buttons = plan.buttons[: settings.MAX_BUTTONS]
        plan.buttons = [
            button
            for button in plan.buttons
            if button.title and (button.url or button.payload)
        ]
        if not plan.buttons:
            plan.type = "text"
            plan.text = plan.text or fallback_for_message_type("text")
    if plan.type == "quick_reply":
        cleaned_replies = []
        for option in plan.quick_replies[: settings.MAX_QUICK_REPLIES]:
            option.title = option.title[: settings.QUICK_REPLY_TITLE_MAX_CHARS].strip()
            option.payload = option.payload[: settings.QUICK_REPLY_PAYLOAD_MAX_CHARS].strip()
            if not option.title or not option.payload:
                continue
            cleaned_replies.append(option)
        plan.quick_replies = cleaned_replies
        if not plan.quick_replies:
            plan.type = "text"
            plan.text = plan.text or fallback_for_message_type("text")
    if plan.type == "generic_template":
        cleaned_elements = []
        for element in plan.elements[: settings.MAX_TEMPLATE_SLIDES]:
            element.title = element.title[:80].strip()
            if not element.title:
                continue
            if element.subtitle:
                element.subtitle = element.subtitle[:80].strip()
            element.buttons = element.buttons[: settings.MAX_BUTTONS]
            cleaned_elements.append(element)
        plan.elements = cleaned_elements
        if not plan.elements:
            plan.type = "text"
            plan.text = fallback_for_message_type("text")

    sender = Sender()

    try:
        response_data = None
        if plan.type == "button":
            response_data = await sender.send_button_text(
                receiver_id, plan.text or "", plan.buttons
            )
        elif plan.type == "quick_reply":
            response_data = await sender.send_quick_reply(
                receiver_id, plan.text or "", plan.quick_replies
            )
        elif plan.type == "generic_template":
            response_data = await sender.send_generic_template(receiver_id, plan.elements)
        elif plan.type == "photo":
            response_data = await sender.send_photo(receiver_id, plan.image_url or "")
        elif plan.type == "video":
            response_data = await sender.send_video(receiver_id, plan.video_url or "")
        elif plan.type == "audio":
            response_data = await sender.send_audio(receiver_id, plan.audio_url or "")
        else:
            response_data = await sender.send_text(receiver_id, plan.text or "")
        message_id = None
        if isinstance(response_data, dict):
            message_id = response_data.get("message_id")
        logger.info(
            "outbound_sent",
            receiver_id=receiver_id,
            message_type=plan.type,
            message_id=message_id,
        )
        await log_event(
            session,
            level="info",
            event_type="outbound_sent",
            message=plan.text,
            data={
                "receiver_id": receiver_id,
                "message_type": plan.type,
                "message_id": message_id,
            },
            commit=False,
        )
        response_meta = {
            "receiver_id": receiver_id,
            "conversation_id": conversation_id,
            "message_type": plan.type,
            "message_id": message_id,
            "source": "unspecified",
        }
        if meta:
            response_meta.update(meta)
        await log_event(
            session,
            level="info",
            event_type="assistant_response",
            message=plan.text,
            data=response_meta,
            commit=False,
        )
    except SenderError as exc:
        logger.error("errors", stage="send", error=str(exc))
        await log_event(
            session,
            level="error",
            event_type="send_error",
            message=str(exc),
            data={"receiver_id": receiver_id, "message_type": plan.type},
        )
        if plan.type == "text":
            return None
        fallback_text = _plan_to_text(plan)
        try:
            response_data = await sender.send_text(receiver_id, fallback_text)
        except SenderError:
            return None
        message_id = None
        if isinstance(response_data, dict):
            message_id = response_data.get("message_id")
        logger.info(
            "outbound_sent",
            receiver_id=receiver_id,
            message_type="text_fallback",
            message_id=message_id,
        )
        await log_event(
            session,
            level="info",
            event_type="outbound_sent",
            message=fallback_text,
            data={
                "receiver_id": receiver_id,
                "message_type": "text_fallback",
                "message_id": message_id,
            },
            commit=False,
        )
        response_meta = {
            "receiver_id": receiver_id,
            "conversation_id": conversation_id,
            "message_type": "text_fallback",
            "message_id": message_id,
            "source": "unspecified",
        }
        if meta:
            response_meta.update(meta)
        await log_event(
            session,
            level="info",
            event_type="assistant_response",
            message=fallback_text,
            data=response_meta,
            commit=False,
        )
        plan = OutboundPlan(type="text", text=fallback_text)

    conversation = await session.get(Conversation, conversation_id)
    if conversation:
        conversation.last_bot_message_at = utc_now()

    record = Message(
        conversation_id=conversation_id,
        role="assistant",
        type=plan.type,
        content_text=plan.text,
        media_url=plan.image_url or plan.video_url or plan.audio_url,
        payload_json=plan.model_dump(),
    )
    session.add(record)
    await session.commit()
    return message_id
