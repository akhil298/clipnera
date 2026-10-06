"""Welcome form answers and the referral program

Accounts that already exist are marked as having done the welcome form,
with no answers, so only accounts created from now on are asked.

Revision ID: 20261007020000
Revises: 20261007010000
Create Date: 2026-10-07 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261007020000"
down_revision: Union[str, None] = "20261007010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_fk(name: str, nullable: bool, ondelete: str = "SET NULL", **kwargs) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey("users.id", ondelete=ondelete), nullable=nullable, **kwargs)


def upgrade() -> None:
    op.create_table(
        "user_onboarding",
        _user_fk("user_id", False, "CASCADE", primary_key=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("role_other", sa.String(80), nullable=True),
        sa.Column("heard_from", sa.String(20), nullable=True),
        sa.Column("heard_from_other", sa.String(80), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
    )
    op.execute("INSERT INTO user_onboarding (user_id, completed_at) SELECT id, now() FROM users")

    op.create_table(
        "referral_codes",
        _user_fk("user_id", False, "CASCADE", primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "referrals",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk("referrer_id", True),
        _user_fk("referee_id", True, unique=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("referee_name", sa.String(120), nullable=False),
        sa.Column("referee_email_masked", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("fail_reason", sa.String(30), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("signed_up_at", sa.DateTime(), nullable=False),
        sa.Column("pro_deadline_at", sa.DateTime(), nullable=False),
        sa.Column("pro_payment_id", sa.String(36), nullable=True),
        sa.Column("pro_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("pro_activated_at", sa.DateTime(), nullable=True),
        sa.Column("video_deadline_at", sa.DateTime(), nullable=True),
        sa.Column("video_project_id", sa.String(36), nullable=True),
        sa.Column("video_started_at", sa.DateTime(), nullable=True),
        sa.Column("video_completed_at", sa.DateTime(), nullable=True),
        sa.Column("review_state", sa.String(10), nullable=False),
        sa.Column("flagged_reason", sa.String(255), nullable=True),
        _user_fk("reviewed_by", True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("pro_reminder_sent_at", sa.DateTime(), nullable=True),
        sa.Column("video_reminder_sent_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_referrals_referrer_created", "referrals", ["referrer_id", "created_at"])
    op.create_index("ix_referrals_status", "referrals", ["status"])

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "referral_id", sa.String(36), sa.ForeignKey("referrals.id", ondelete="CASCADE"), nullable=False
        ),
        _user_fk("recipient_id", False, "CASCADE"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column(
            "grant_id", sa.String(36), sa.ForeignKey("credit_grants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("referral_id", "kind", name="uq_referral_rewards_referral_kind"),
    )
    op.create_index("ix_referral_rewards_referral_id", "referral_rewards", ["referral_id"])
    op.create_index("ix_referral_rewards_recipient_id", "referral_rewards", ["recipient_id"])

    op.create_table(
        "referred_emails",
        sa.Column("email_hash", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "referral_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referee_pro_credits", sa.Integer(), nullable=False),
        sa.Column("referrer_pro_credits", sa.Integer(), nullable=False),
        sa.Column("referrer_video_credits", sa.Integer(), nullable=False),
        sa.Column("bonus_expiry_days", sa.Integer(), nullable=False),
        sa.Column("pro_window_hours", sa.Integer(), nullable=False),
        sa.Column("video_window_hours", sa.Integer(), nullable=False),
        sa.Column("monthly_cap", sa.Integer(), nullable=False),
        sa.Column("min_video_seconds", sa.Integer(), nullable=False),
        sa.Column("approval_wait_days", sa.Integer(), nullable=False),
        _user_fk("updated_by", True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_referral_settings_single_row"),
    )

    op.create_table(
        "referral_settings_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk("admin_id", True),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "referral_settings_changes",
        "referral_settings",
        "referred_emails",
        "referral_rewards",
        "referrals",
        "referral_codes",
        "user_onboarding",
    ):
        op.drop_table(table)
