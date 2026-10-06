from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class UserOnboarding(Base):
    """What a user told us when they first signed in: what they do and how
    they heard about Clipnera. One row per user, written once.

    Accounts that existed before the form were marked done without answers
    (role and heard_from null), so only new accounts are asked."""

    __tablename__ = "user_onboarding"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role_other: Mapped[str | None] = mapped_column(String(80), nullable=True)
    heard_from: Mapped[str | None] = mapped_column(String(20), nullable=True)
    heard_from_other: Mapped[str | None] = mapped_column(String(80), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
