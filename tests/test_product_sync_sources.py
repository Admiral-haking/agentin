import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("DIRECTAM_BASE_URL", "https://directam.example.com")
os.environ.setdefault("SERVICE_API_KEY", "test")

from app.models.product import ProductAvailability
from app.services.product_sync import _mongo_doc_to_product, _price_snapshot_from_mongo_doc


def test_price_snapshot_from_mongo_doc_respects_active_offer() -> None:
    now = datetime.now(timezone.utc)
    doc = {
        "variants": [
            {
                "active": True,
                "price": {"amount": 500000},
                "offer": {
                    "amount": 100000,
                    "startsAt": (now - timedelta(hours=2)).isoformat(),
                    "endsAt": (now + timedelta(hours=2)).isoformat(),
                },
                "inventory": {"quantity": 3},
            },
            {
                "active": True,
                "price": {"amount": 420000},
                "inventory": {"quantity": 0},
            },
        ]
    }
    price, old_price, availability = _price_snapshot_from_mongo_doc(doc, now=now)
    assert price == 400000
    assert old_price == 500000
    assert availability == ProductAvailability.instock


def test_mongo_doc_to_product_builds_page_url() -> None:
    now = datetime.now(timezone.utc)
    doc = {
        "_id": "65f2a4d92f6d7f0d31e6f001",
        "slug": "classic-boot",
        "variants": [
            {
                "active": True,
                "price": {"amount": 200000},
                "inventory": {"quantity": 0},
            }
        ],
    }
    mapped = _mongo_doc_to_product(doc, "https://ghlbedovom.com", now=now)
    assert mapped is not None
    assert mapped.page_url == "https://ghlbedovom.com/product/classic-boot"
    assert mapped.product_id == "65f2a4d92f6d7f0d31e6f001"
    assert mapped.price == 200000
    assert mapped.availability == ProductAvailability.outofstock
