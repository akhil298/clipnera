"""Connected social accounts disconnect themselves 7 days after connecting

Revision ID: 20260929010000
Revises: 20260928010000
Create Date: 2026-09-29 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260929010000"
down_revision: Union[str, None] = "20260928010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE social_audit_action ADD VALUE IF NOT EXISTS 'expired'")
    op.add_column("connected_accounts", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("connected_accounts", sa.Column("expiry_warned_at", sa.DateTime(), nullable=True))
    # Accounts connected before this change get a full week from now.
    op.execute(
        "UPDATE connected_accounts SET expires_at = (now() at time zone 'utc') + interval '7 days' "
        "WHERE status IN ('active', 'needs_reconnect')"
    )
    op.create_index("ix_connected_accounts_expires_at", "connected_accounts", ["expires_at"])


def downgrade() -> None:
    # Postgres cannot drop an enum value; 'expired' stays in social_audit_action.
    op.drop_index("ix_connected_accounts_expires_at", table_name="connected_accounts")
    op.drop_column("connected_accounts", "expiry_warned_at")
    op.drop_column("connected_accounts", "expires_at")
