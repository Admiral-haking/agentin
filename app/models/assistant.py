from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AssistantConversation(TimestampMixin, Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    context: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20), default="hybrid")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    admin = relationship("AdminUser")
    messages = relationship(
        "AssistantMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    actions = relationship("AssistantAction", back_populates="conversation")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(20))
    usage_json: Mapped[dict | None] = mapped_column(JSONB)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation = relationship("AssistantConversation", back_populates="messages")


class AssistantAction(TimestampMixin, Base):
    __tablename__ = "assistant_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistant_conversations.id"), index=True
    )
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    action_type: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(String(255))
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversation = relationship("AssistantConversation", back_populates="actions")
    admin = relationship("AdminUser", foreign_keys=[admin_id])
    approver = relationship("AdminUser", foreign_keys=[approved_by])
