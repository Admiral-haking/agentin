from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120))
    price_range: Mapped[str | None] = mapped_column(String(120))
    sizes: Mapped[list[str] | None] = mapped_column(JSONB)
    colors: Mapped[list[str] | None] = mapped_column(JSONB)
    images: Mapped[list[str] | None] = mapped_column(JSONB)
    link: Mapped[str | None] = mapped_column(Text)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
