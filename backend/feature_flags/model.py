from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    event,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

# Admin permissions (06-flags §6.2). The migration grants every one to every existing admin.
FLAGS_VIEW = "flags.view"
FLAGS_KILL = "flags.kill"
FLAGS_EDIT = "flags.edit"
CONFIG_EDIT = "config.edit"
SEGMENTS_EDIT = "segments.edit"
ALL_PERMISSIONS = (FLAGS_VIEW, FLAGS_KILL, FLAGS_EDIT, CONFIG_EDIT, SEGMENTS_EDIT)

STATE_ROW_ID = 1
NOTIFY_CHANNEL = "flags_changed"


class FeatureFlag(Base):
    """Stored state for a flag in feature_flags/registry.py. No row means the definition's default.

    ``enabled`` is the targeting switch: off means off for everyone. ``rollout_bps``
    defaults to 100%, so a row that was simply switched on stays on for everyone.
    """

    __tablename__ = "feature_flags"
    __table_args__ = (CheckConstraint("rollout_bps BETWEEN 0 AND 10000", name="ck_feature_flags_rollout_bps"),)

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    rollout_bps: Mapped[int] = mapped_column(Integer, default=10000, server_default="10000", nullable=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    bucket_salt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    killed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    killed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    killed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    killed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)


class TargetingOverride(Base):
    """A value forced for one user or workspace, on a flag or a config key."""

    __tablename__ = "targeting_overrides"
    __table_args__ = (Index("ix_targeting_overrides_subject", "subject_type", "subject_id"),)

    target_kind: Mapped[str] = mapped_column(String(16), primary_key=True)    # flag | config
    target_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(16), primary_key=True)   # user | workspace
    subject_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FlagSegment(Base):
    """A named audience for rules: matched by user id, email domain or role."""

    __tablename__ = "flag_segments"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    user_ids: Mapped[list[str]] = mapped_column(ARRAY(String(36)), default=list, server_default="{}", nullable=False)
    email_domains: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), default=list, server_default="{}", nullable=False
    )
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list, server_default="{}", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False
    )


class RemoteConfig(Base):
    """Stored state for a key in feature_flags/config_registry.py. No row means the code default."""

    __tablename__ = "remote_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    default_value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FlagStateVersion(Base):
    """One row: bumped by every flag/config write so every process knows to reload."""

    __tablename__ = "flag_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)


class FlagAuditLog(Base):
    """Every admin change to flags, config and segments. Append-only, enforced by a trigger."""

    __tablename__ = "flag_audit_log"
    __table_args__ = (Index("ix_flag_audit_log_target", "target_key", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # A snapshot, so history stays readable after the admin is deleted.
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_key: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(32), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


# Databases built with Base.metadata.create_all (tests) get the same trigger and
# seed rows as the migrations. The migrations keep their own frozen copy.
event.listen(
    FlagAuditLog.__table__,
    "after_create",
    DDL(
        "CREATE OR REPLACE FUNCTION flag_audit_log_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'flag_audit_log is append-only'; END $$"
    ),
)
event.listen(
    FlagAuditLog.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER flag_audit_log_append_only BEFORE UPDATE OR DELETE ON flag_audit_log "
        "FOR EACH ROW EXECUTE FUNCTION flag_audit_log_reject_change()"
    ),
)
event.listen(
    FlagAuditLog.__table__,
    "after_drop",
    DDL("DROP FUNCTION IF EXISTS flag_audit_log_reject_change()"),
)
event.listen(
    FlagStateVersion.__table__,
    "after_create",
    DDL(f"INSERT INTO flag_state (id, version) VALUES ({STATE_ROW_ID}, 1)"),
)
event.listen(
    FlagSegment.__table__,
    "after_create",
    DDL(
        "INSERT INTO flag_segments (key, description, roles) VALUES "
        "('staff', 'Admins, plus the users listed here.', '{admin}'), "
        "('beta', 'People who opted in to early features.', '{}')"
    ),
)

