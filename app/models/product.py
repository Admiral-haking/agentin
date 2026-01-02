from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProductAvailability(str, Enum):
    instock = "instock"
    outofstock = "outofstock"
    unknown = "unknown"


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    page_url: Mapped[str | None] = mapped_column(Text, unique=True)
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    images: Mapped[list[str] | None] = mapped_column(JSONB)
    price: Mapped[int | None] = mapped_column(Integer)
    old_price: Mapped[int | None] = mapped_column(Integer)
    availability: Mapped[ProductAvailability] = mapped_column(
        SAEnum(ProductAvailability, name="product_availability"),
        default=ProductAvailability.unknown,
    )
    lastmod: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_flags: Mapped[dict | None] = mapped_column(JSONB, default=dict)
