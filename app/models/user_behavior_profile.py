from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserBehaviorProfile(TimestampMixin, Base):
    __tablename__ = "user_behavior_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    last_pattern: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column()
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pattern_history: Mapped[list[dict] | None] = mapped_column(JSONB)

    user = relationship("User", back_populates="behavior_profile")
