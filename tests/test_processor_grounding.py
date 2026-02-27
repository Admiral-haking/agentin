import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("DIRECTAM_BASE_URL", "https://directam.example.com")
os.environ.setdefault("SERVICE_API_KEY", "test")

from app.services.processor import (
    _allowed_price_values,
    _remember_user_context,
    _reply_has_ungrounded_price,
)


def test_reply_price_grounding_blocks_unknown_prices() -> None:
    assert _reply_has_ungrounded_price("قیمتش 420,000 تومنه", {390000}) is True
    assert _reply_has_ungrounded_price("قیمتش 390,000 تومنه", {390000}) is False


def test_reply_price_grounding_accepts_rial_toman_mismatch() -> None:
    # 390,000 toman is commonly represented as 3,900,000 rial.
    assert _reply_has_ungrounded_price("قیمت 390000 تومان", {3900000}) is False


def test_remember_user_context_updates_recent_queries_and_products() -> None:
    products = [
        SimpleNamespace(slug="classic-boot", price=390000, old_price=420000),
        SimpleNamespace(slug="daily-sandal", price=210000, old_price=None),
    ]
    profile, changed = _remember_user_context(
        profile_json={"prefs": {"gender": "خانم"}},
        user_text="بوت زنانه میخوام",
        matched_products=products,
        selected_product={"slug": "classic-boot"},
    )
    assert changed is True
    assert profile is not None
    memory = profile.get("memory")
    assert isinstance(memory, dict)
    assert memory.get("recent_queries")
    assert "classic-boot" in (memory.get("recent_product_slugs") or [])


def test_allowed_price_values_collects_product_and_selected_prices() -> None:
    products = [SimpleNamespace(price=100000, old_price=120000)]
    selected = {"price": 130000, "old_price": 150000}
    values = _allowed_price_values(products, selected)
    assert values == {100000, 120000, 130000, 150000}
