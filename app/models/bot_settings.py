from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BotSettings(TimestampMixin, Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_mode: Mapped[str] = mapped_column(String(20), default="hybrid")
    system_prompt: Mapped[str | None] = mapped_column(Text)
    admin_notes: Mapped[str | None] = mapped_column(Text)
    max_history_messages: Mapped[int] = mapped_column(Integer, default=20)
    max_output_chars: Mapped[int] = mapped_column(Integer, default=800)
    fallback_text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), default="fa")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    followup_enabled: Mapped[bool | None] = mapped_column(Boolean)
    followup_delay_hours: Mapped[int | None] = mapped_column(Integer)
    followup_message: Mapped[str | None] = mapped_column(Text)
