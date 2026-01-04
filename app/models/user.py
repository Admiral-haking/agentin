from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    follow_status: Mapped[str | None] = mapped_column(String(50))
    follower_count: Mapped[int | None] = mapped_column(Integer)
    profile_json: Mapped[dict | None] = mapped_column(JSONB)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_score: Mapped[int] = mapped_column(Integer, default=0)
    followup_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)

    conversations = relationship("Conversation", back_populates="user")
    behavior_profile = relationship("UserBehaviorProfile", back_populates="user", uselist=False)
