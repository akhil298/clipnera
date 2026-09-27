"""Credit packs: bought credits that never expire

Revision ID: 20260927040000
Revises: 20260927030000
Create Date: 2026-09-27 04:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260927040000"
down_revision: Union[str, None] = "20260927030000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLAN_OR_PACK = "ck_payment_transactions_plan_or_credit_pack"


def upgrade() -> None:
    op.add_column(
        "credit_ledger",
        sa.Column("purchased_balance_after", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "credit_ledger",
        sa.Column("purchased_amount", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column("payment_transactions", sa.Column("credit_pack", sa.String(length=20), nullable=True))
    op.add_column("payment_transactions", sa.Column("credits", sa.Integer(), nullable=True))
    op.alter_column("payment_transactions", "plan_id", existing_type=sa.String(length=36), nullable=True)
    op.alter_column(
        "payment_transactions",
        "plan_type",
        existing_type=sa.Enum("monthly", "yearly", name="billing_period"),
        nullable=True,
        server_default=None,
    )
    op.create_check_constraint(
        PLAN_OR_PACK,
        "payment_transactions",
        "(plan_id IS NOT NULL AND plan_type IS NOT NULL AND credit_pack IS NULL AND credits IS NULL)"
        " OR (plan_id IS NULL AND plan_type IS NULL AND credit_pack IS NOT NULL AND credits > 0)",
    )


def downgrade() -> None:
    op.drop_constraint(PLAN_OR_PACK, "payment_transactions", type_="check")
    # Credit-pack payments have no plan and cannot survive the NOT NULL below.
    op.execute("DELETE FROM payment_transactions WHERE credit_pack IS NOT NULL")
    op.alter_column(
        "payment_transactions",
        "plan_type",
        existing_type=sa.Enum("monthly", "yearly", name="billing_period"),
        nullable=False,
        server_default="monthly",
    )
    op.alter_column("payment_transactions", "plan_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_column("payment_transactions", "credits")
    op.drop_column("payment_transactions", "credit_pack")
    op.drop_column("credit_ledger", "purchased_amount")
    op.drop_column("credit_ledger", "purchased_balance_after")
