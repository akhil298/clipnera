from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import String, Boolean, Date, ForeignKey, Enum, DateTime, Index, Text, false as sa_false, true as sa_true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class AuthProvider(str, enum.Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda obj: [e.value for e in obj]),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
        nullable=False,
    )
    # Set for accounts that existed before Pro gating, so they are told once
    # which features moved to Pro. Cleared when the notice is dismissed.
    plan_notice_pending: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false(), nullable=False
    )
    # When the user confirmed they are 18+ and accepted the Terms and Privacy
    # Policy. Null for accounts created before sign-up asked.
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Account emails (failed posts, reconnect reminders). Off after unsubscribing.
    email_notifications: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=sa_true(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    accounts: Mapped[list["UserAccount"]] = relationship(
        "UserAccount", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="accounts", lazy="selectin")


class LoginEvent(Base):
    """One row per successful sign-in, for the admin panel's login history."""

    __tablename__ = "login_events"
    __table_args__ = (
        Index("ix_login_events_user_created", "user_id", "created_at"),
        Index("ix_login_events_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # An AuthProvider value: how the user proved who they are.
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UserActivityDay(Base):
    """The user made at least one signed-in request on this UTC day.

    Tokens last for days, so logins undercount who actually uses the app; this
    is what daily, weekly and monthly active users are counted from.
    """

    __tablename__ = "user_activity_days"
    __table_args__ = (Index("ix_user_activity_days_day", "day"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
