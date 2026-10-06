"""Bonus credits: grants that expire on their own dates

Adds the bonus part of the balance to every ledger entry, the grants it is
made of, and which ledger entries used or gave back which grant.

Revision ID: 20261007010000
Revises: 20261006020000
Create Date: 2026-10-07 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261007010000"
down_revision: Union[str, None] = "20261006020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credit_ledger", sa.Column("bonus_balance_after", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("credit_ledger", sa.Column("bonus_amount", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "credit_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("expired_at", sa.DateTime(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("remaining >= 0 AND remaining <= amount", name="ck_credit_grants_remaining"),
    )
    op.create_index("ix_credit_grants_user_open", "credit_grants", ["user_id", "expires_at"])
    op.create_index("ix_credit_grants_reference_id", "credit_grants", ["reference_id"])

    op.create_table(
        "credit_grant_spends",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "ledger_id", sa.String(36), sa.ForeignKey("credit_ledger.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "grant_id", sa.String(36), sa.ForeignKey("credit_grants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
    )
    op.create_index("ix_credit_grant_spends_ledger_id", "credit_grant_spends", ["ledger_id"])
    op.create_index("ix_credit_grant_spends_grant_id", "credit_grant_spends", ["grant_id"])


def downgrade() -> None:
    op.drop_table("credit_grant_spends")
    op.drop_table("credit_grants")
    op.drop_column("credit_ledger", "bonus_amount")
    op.drop_column("credit_ledger", "bonus_balance_after")
