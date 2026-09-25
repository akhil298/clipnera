"""Connected publishing platforms and admin feature flags

Revision ID: 20260926000000
Revises: 20260925020000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260926000000"
down_revision: Union[str, None] = "20260925020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    # create_type=False: created explicitly below so each type is made once.
    return postgresql.ENUM(*values, name=name, create_type=False)


social_platform = _enum("social_platform", "youtube", "tiktok", "instagram", "x")
account_status = _enum("social_account_status", "active", "needs_reconnect", "disconnecting", "disconnected")
post_status = _enum("scheduled_post_status", "scheduled", "publishing", "published", "failed", "cancelled")
audit_action = _enum(
    "social_audit_action",
    "connected",
    "reconnected",
    "disconnected",
    "force_disconnected",
    "deauthorized",
    "data_deleted",
    "needs_reconnect",
    "post_scheduled",
    "post_published",
    "post_failed",
    "post_cancelled",
)
ENUMS = (social_platform, account_status, post_status, audit_action)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", social_platform, nullable=False),
        sa.Column("platform_user_id", sa.String(255), nullable=False),
        sa.Column("handle", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("follower_count_updated_at", sa.DateTime(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("status", account_status, nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_connected_accounts_user_id", "connected_accounts", ["user_id"])
    op.create_index(
        "uq_connected_accounts_platform_user_live",
        "connected_accounts",
        ["platform", "platform_user_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'disconnected'"),
    )

    op.create_table(
        "oauth_tokens",
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("access_token_ct", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_ct", sa.LargeBinary(), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=True),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("refresh_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_verifier_ct", sa.LargeBinary(), nullable=True),
        sa.Column("key_version", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", social_platform, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])

    op.create_table(
        "scheduled_posts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "clip_id", sa.String(36), sa.ForeignKey("generated_clips.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("publish_group_id", sa.String(36), nullable=False),
        sa.Column("platform", social_platform, nullable=False),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("platform_options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", post_status, nullable=False),
        sa.Column("platform_publish_id", sa.Text(), nullable=True),
        sa.Column("platform_post_id", sa.String(255), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_scheduled_posts_user_id", "scheduled_posts", ["user_id"])
    op.create_index("ix_scheduled_posts_account_id", "scheduled_posts", ["account_id"])
    op.create_index("ix_scheduled_posts_clip_id", "scheduled_posts", ["clip_id"])
    op.create_index("ix_scheduled_posts_publish_group_id", "scheduled_posts", ["publish_group_id"])
    op.create_index("ix_scheduled_posts_due", "scheduled_posts", ["status", "next_attempt_at"])
    op.create_index("ix_scheduled_posts_user_created", "scheduled_posts", ["user_id", "created_at"])

    op.create_table(
        "publish_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("post_id", sa.String(36), nullable=True),
        sa.Column("platform", social_platform, nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_publish_audit_log_user_id", "publish_audit_log", ["user_id"])
    op.create_index("ix_publish_audit_log_account_id", "publish_audit_log", ["account_id"])
    op.create_index("ix_publish_audit_log_created_at", "publish_audit_log", ["created_at"])

    op.create_table(
        "platform_quota_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("platform", social_platform, nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("platform", "scope_key", "window_start", name="uq_platform_quota_usage_window"),
    )

    op.create_table(
        "social_data_deletion_requests",
        sa.Column("confirmation_code", sa.String(32), primary_key=True),
        sa.Column("platform", social_platform, nullable=False),
        sa.Column("accounts_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("social_data_deletion_requests")
    op.drop_table("platform_quota_usage")
    op.drop_index("ix_publish_audit_log_created_at", table_name="publish_audit_log")
    op.drop_index("ix_publish_audit_log_account_id", table_name="publish_audit_log")
    op.drop_index("ix_publish_audit_log_user_id", table_name="publish_audit_log")
    op.drop_table("publish_audit_log")
    op.drop_table("scheduled_posts")
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_table("oauth_tokens")
    op.drop_index("uq_connected_accounts_platform_user_live", table_name="connected_accounts")
    op.drop_index("ix_connected_accounts_user_id", table_name="connected_accounts")
    op.drop_table("connected_accounts")
    op.drop_table("feature_flags")
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
