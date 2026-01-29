from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AdminMediaNote(TimestampMixin, Base):
    __tablename__ = "admin_media_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id"), index=True
    )
    media_url: Mapped[str] = mapped_column(Text)
    tag: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(32))
