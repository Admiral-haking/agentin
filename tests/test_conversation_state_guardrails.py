import os

# Ensure required settings are present before importing app modules.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("DIRECTAM_BASE_URL", "https://directam.example.com")
os.environ.setdefault("SERVICE_API_KEY", "test")

from app.schemas.send import OutboundPlan
from app.services.guardrails import validate_reply_or_rewrite
from app.services.processor import resolve_repeat_plan


def test_link_request_returns_selected_product_url() -> None:
    plan = OutboundPlan(type="text", text="متن تست")
    state = {"selected_product": {"page_url": "https://example.com/product/abc"}}
    updated, reasons = validate_reply_or_rewrite(
        plan,
        state,
        "لینک محصول رو بده",
        has_products_context=False,
        allow_generic_slots=False,
    )
    assert "https://example.com/product/abc" in (updated.text or "")
    assert "link_request_handled" in reasons


def test_selected_product_blocks_generic_slots() -> None:
    plan = OutboundPlan(
        type="text",
        text="برای معرفی دقیق‌تر، لطفاً جنسیت، سایز، سبک و بودجه رو بگید.",
    )
    state = {"selected_product": {"page_url": "https://example.com/product/abc"}}
    updated, reasons = validate_reply_or_rewrite(
        plan,
        state,
        "اینو میخوام",
        has_products_context=True,
        allow_generic_slots=True,
    )
    assert "جنسیت" not in (updated.text or "")
    assert "ثبت سفارش" in (updated.text or "")
    assert "template_blocked:selected_product" in reasons


def test_repeat_plan_uses_cached_answer() -> None:
    plan, meta = resolve_repeat_plan(
        store_topic=None,
        last_bot_action="product_link",
        last_bot_answers={"product_link": "لینک مستقیم محصول: https://example.com/p/1"},
        last_assistant_text="fallback",
    )
    assert plan is not None
    assert "https://example.com/p/1" in (plan.text or "")
    assert meta.get("repeat_source") == "cached_intent"


def test_link_request_missing_page_url_prompts_for_name() -> None:
    plan = OutboundPlan(type="text", text="هر متن دیگری")
    updated, reasons = validate_reply_or_rewrite(
        plan,
        None,
        "لینک محصول رو بده",
        has_products_context=False,
        allow_generic_slots=False,
    )
    assert "اسم دقیق" in (updated.text or "")
    assert "جنسیت" not in (updated.text or "")
    assert "link_request_missing" in reasons


def test_guardrail_blocks_hallucinated_prices_and_options() -> None:
    plan = OutboundPlan(type="text", text="شماره 01 قیمت 300 هزار تومان")
    updated, reasons = validate_reply_or_rewrite(
        plan,
        None,
        "قیمتش چنده",
        has_products_context=False,
        allow_generic_slots=False,
    )
    assert "اسم/مدل" in (updated.text or "")
    assert any(reason.startswith("hallucination_prevented") for reason in reasons)
