"""Login history and daily activity, for the admin panel

Revision ID: 20260927030000
Revises: 20260927020000
Create Date: 2026-09-27 03:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260927030000"
down_revision: Union[str, None] = "20260927020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_login_events_user_created", "login_events", ["user_id", "created_at"])
    op.create_index("ix_login_events_created", "login_events", ["created_at"])

    op.create_table(
        "user_activity_days",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
    )
    op.create_index("ix_user_activity_days_day", "user_activity_days", ["day"])

    # The admin panel sums AI spend per user.
    op.create_index("ix_llm_usage_user", "llm_usage", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_user", table_name="llm_usage")
    op.drop_index("ix_user_activity_days_day", table_name="user_activity_days")
    op.drop_table("user_activity_days")
    op.drop_index("ix_login_events_created", table_name="login_events")
    op.drop_index("ix_login_events_user_created", table_name="login_events")
    op.drop_table("login_events")
