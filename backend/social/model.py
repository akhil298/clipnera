"""Connected publishing platforms: accounts, their tokens, and posts.

Timestamps are naive UTC, like the rest of the schema.

Tokens live in their own table with no ORM relationship from ConnectedAccount,
so no account query, serializer or admin view can load them by accident. Only
social/tokens.py reads that table.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _values(enum_cls: type[enum.Enum]) -> list[str]:
    return [e.value for e in enum_cls]


class SocialPlatform(str, enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    X = "x"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"
    # Disconnect requested; the worker revokes the grant and deletes the tokens.
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"


class PostStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditAction(str, enum.Enum):
    CONNECTED = "connected"
    RECONNECTED = "reconnected"
    DISCONNECTED = "disconnected"
    FORCE_DISCONNECTED = "force_disconnected"
    DEAUTHORIZED = "deauthorized"
    DATA_DELETED = "data_deleted"
    NEEDS_RECONNECT = "needs_reconnect"
    POST_SCHEDULED = "post_scheduled"
    POST_PUBLISHED = "post_published"
    POST_FAILED = "post_failed"
    POST_CANCELLED = "post_cancelled"


_platform_enum = Enum(SocialPlatform, name="social_platform", values_callable=_values)


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"
    __table_args__ = (
        # One platform account can be linked to one Clipnera user at a time.
        Index(
            "uq_connected_accounts_platform_user_live",
            "platform",
            "platform_user_id",
            unique=True,
            postgresql_where=text("status <> 'disconnected'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[SocialPlatform] = mapped_column(_platform_enum, nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follower_count_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="social_account_status", values_callable=_values),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class OAuthToken(Base):
    """Encrypted credentials for one connected account. See core/crypto.py."""

    __tablename__ = "oauth_tokens"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connected_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    access_token_ct: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_ct: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    refresh_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class OAuthState(Base):
    """A pending connect attempt. The state value itself is only stored hashed."""

    __tablename__ = "oauth_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code_verifier_ct: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    key_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[SocialPlatform] = mapped_column(_platform_enum, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    __table_args__ = (
        Index("ix_scheduled_posts_due", "status", "next_attempt_at"),
        Index("ix_scheduled_posts_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generated_clips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Posts created together (one clip to several accounts) share a group id.
    publish_group_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    platform: Mapped[SocialPlatform] = mapped_column(_platform_enum, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    platform_options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="scheduled_post_status", values_callable=_values),
        default=PostStatus.SCHEDULED,
        nullable=False,
    )
    # The platform's handle on an in-flight upload (TikTok publish_id, IG
    # container id, X media id, YouTube session URI), saved before the final
    # publish call so a crashed run can find out what happened instead of posting twice.
    platform_publish_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PublishAuditLog(Base):
    """Who connected, disconnected, published or deleted what. Never holds token values."""

    __tablename__ = "publish_audit_log"
    __table_args__ = (Index("ix_publish_audit_log_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="social_audit_action", values_callable=_values), nullable=False
    )
    # "user", "admin", "system" (the worker) or "webhook" (a platform).
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    post_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    platform: Mapped[SocialPlatform | None] = mapped_column(_platform_enum, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PlatformQuotaUsage(Base):
    """Calls counted against a platform quota window (app-wide or per account)."""

    __tablename__ = "platform_quota_usage"
    __table_args__ = (
        UniqueConstraint("platform", "scope_key", "window_start", name="uq_platform_quota_usage_window"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    platform: Mapped[SocialPlatform] = mapped_column(_platform_enum, nullable=False)
    # "app" for project-wide quotas, otherwise an account id.
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Money spent in this window, for platforms that bill per call (X).
    cost_micros: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class DataDeletionRequest(Base):
    """A platform-initiated deletion (Meta requires a status page and confirmation code)."""

    __tablename__ = "social_data_deletion_requests"

    confirmation_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    platform: Mapped[SocialPlatform] = mapped_column(_platform_enum, nullable=False)
    accounts_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
