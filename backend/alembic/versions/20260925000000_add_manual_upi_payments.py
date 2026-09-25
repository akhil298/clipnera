"""add manual UPI payments: user roles, INR plan prices, payment proof columns

Revision ID: 20260925000000
Revises: 20260924000000
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260925000000"
down_revision: Union[str, None] = "20260924000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role = sa.Enum("user", "admin", name="user_role")


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("role", user_role, nullable=False, server_default="user"),
    )

    op.add_column("plans", sa.Column("price_inr", sa.Numeric(10, 2), nullable=True))

    op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'rejected'")

    op.add_column("payment_transactions", sa.Column("utr_number", sa.String(30), nullable=True))
    op.add_column("payment_transactions", sa.Column("screenshot_key", sa.Text(), nullable=True))
    op.add_column("payment_transactions", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("payment_transactions", sa.Column("verified_by", sa.String(36), nullable=True))
    op.create_unique_constraint(
        "uq_payment_transactions_utr_number", "payment_transactions", ["utr_number"]
    )
    op.create_foreign_key(
        "fk_payment_transactions_verified_by_users",
        "payment_transactions",
        "users",
        ["verified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_payment_transactions_status_created_at",
        "payment_transactions",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_status_created_at", table_name="payment_transactions")
    op.drop_constraint(
        "fk_payment_transactions_verified_by_users", "payment_transactions", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_payment_transactions_utr_number", "payment_transactions", type_="unique"
    )
    op.drop_column("payment_transactions", "verified_by")
    op.drop_column("payment_transactions", "rejection_reason")
    op.drop_column("payment_transactions", "screenshot_key")
    op.drop_column("payment_transactions", "utr_number")
    # Postgres cannot drop a single enum value, so 'rejected' stays on payment_status.
    op.drop_column("plans", "price_inr")
    op.drop_column("users", "role")
    user_role.drop(op.get_bind(), checkfirst=True)
