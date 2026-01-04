from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ConversationState(TimestampMixin, Base):
    __tablename__ = "conversation_states"

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), primary_key=True
    )
    current_intent: Mapped[str | None] = mapped_column(String(32))
    current_category: Mapped[str | None] = mapped_column(String(32))
    required_slots: Mapped[list[str] | None] = mapped_column(JSONB)
    filled_slots: Mapped[dict | None] = mapped_column(JSONB)
    last_user_question: Mapped[str | None] = mapped_column(String(500))
    last_bot_action: Mapped[str | None] = mapped_column(String(64))
    last_bot_answers: Mapped[dict | None] = mapped_column(JSONB)

    conversation = relationship("Conversation", back_populates="state")
