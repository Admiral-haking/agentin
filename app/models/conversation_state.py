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
    intent: Mapped[str | None] = mapped_column("current_intent", String(32))
    category: Mapped[str | None] = mapped_column("current_category", String(32))
    slots_required: Mapped[list[str] | None] = mapped_column("required_slots", JSONB)
    slots_filled: Mapped[dict | None] = mapped_column("filled_slots", JSONB)
    last_user_question: Mapped[str | None] = mapped_column(String(500))
    last_user_message_id: Mapped[int | None] = mapped_column(Integer)
    last_bot_action: Mapped[str | None] = mapped_column(String(64))
    last_bot_answer_by_intent: Mapped[dict | None] = mapped_column("last_bot_answers", JSONB)
    selected_product: Mapped[dict | None] = mapped_column(JSONB)
    last_handler_used: Mapped[str | None] = mapped_column(String(64))
    loop_counter: Mapped[int] = mapped_column(Integer, default=0)

    conversation = relationship("Conversation", back_populates="state")
