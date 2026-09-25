"""Free vs Pro plans: billing periods, usage tracking, credit cycles

Revision ID: 20260925020000
Revises: 20260925010000
Create Date: 2026-09-25 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260925020000"
down_revision: Union[str, None] = "20260925010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


billing_period = sa.Enum("monthly", "yearly", name="billing_period")

# Timestamps in this schema are naive UTC.
NOW_UTC = "timezone('utc', now())"
CYCLE_SECONDS = 30 * 24 * 60 * 60


def _cycle_start(anchor: str) -> str:
    """SQL for the start date of the 30-day credit cycle containing now.

    Must match SubscriptionService._cycle_start in Python.
    """
    return (
        f"({anchor} + floor(extract(epoch from ({NOW_UTC} - {anchor})) / {CYCLE_SECONDS})"
        f" * interval '30 days')::date"
    )


ACTIVE_PAID_SUBSCRIPTIONS = f"""
    FROM user_subscriptions s
    JOIN plans p ON p.id = s.plan_id
    WHERE s.status = 'active'
      AND s.current_period_start <= {NOW_UTC}
      AND s.current_period_end > {NOW_UTC}
      AND p.slug <> 'free'
"""

NEW_ID = "md5(random()::text || clock_timestamp()::text)::uuid::text"


def upgrade() -> None:
    billing_period.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "payment_transactions",
        sa.Column("plan_type", billing_period, nullable=False, server_default="monthly"),
    )

    op.add_column(
        "users",
        sa.Column("plan_notice_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "usage_tracking",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_key", sa.String(64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "feature_key", "period_start", name="uq_usage_tracking_user_feature_period"),
    )
    op.create_index("ix_usage_tracking_user_id", "usage_tracking", ["user_id"])

    # Prices and allowances now come from subscription/entitlements.py; keep the
    # rows in step for anything that still displays them. Pro Plus is no longer
    # sold, but its subscription rows are left untouched.
    op.execute("UPDATE plans SET credit_minutes = 600, price_inr = 499 WHERE slug = 'pro'")
    op.execute("UPDATE plans SET is_active = false WHERE slug = 'pro_plus'")

    # Mark the current credit cycle as already granted for everyone, so the
    # first reset happens at the next cycle boundary rather than at deploy.
    op.execute(
        f"""
        INSERT INTO usage_tracking (id, user_id, feature_key, count, period_start, created_at, updated_at)
        SELECT {NEW_ID}, u.id, 'credit_refill:free', 1, {_cycle_start('u.created_at')}, {NOW_UTC}, {NOW_UTC}
        FROM users u
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO usage_tracking (id, user_id, feature_key, count, period_start, created_at, updated_at)
        SELECT {NEW_ID}, s.user_id, 'credit_refill:' || s.id, 1,
               {_cycle_start('s.current_period_start')}, {NOW_UTC}, {NOW_UTC}
        {ACTIVE_PAID_SUBSCRIPTIONS}
        ON CONFLICT DO NOTHING
        """
    )

    # Existing free users are told once which features moved to Pro.
    op.execute(
        f"""
        UPDATE users SET plan_notice_pending = true
        WHERE id NOT IN (SELECT s.user_id {ACTIVE_PAID_SUBSCRIPTIONS})
        """
    )


def downgrade() -> None:
    op.execute("UPDATE plans SET is_active = true WHERE slug = 'pro_plus'")
    op.execute("UPDATE plans SET credit_minutes = 300 WHERE slug = 'pro'")
    op.drop_index("ix_usage_tracking_user_id", table_name="usage_tracking")
    op.drop_table("usage_tracking")
    op.drop_column("users", "plan_notice_pending")
    op.drop_column("payment_transactions", "plan_type")
    billing_period.drop(op.get_bind(), checkfirst=True)
