"""add created_by to credit_ledger for admin top-up auditing

Revision ID: 20260925010000
Revises: 20260925000000
Create Date: 2026-09-25 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260925010000"
down_revision: Union[str, None] = "20260925000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("credit_ledger", sa.Column("created_by", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_credit_ledger_created_by_users",
        "credit_ledger",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_credit_ledger_reference_type_created_at",
        "credit_ledger",
        ["reference_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_ledger_reference_type_created_at", table_name="credit_ledger")
    op.drop_constraint("fk_credit_ledger_created_by_users", "credit_ledger", type_="foreignkey")
    op.drop_column("credit_ledger", "created_by")
