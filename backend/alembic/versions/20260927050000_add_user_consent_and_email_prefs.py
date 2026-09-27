"""Users: terms/age consent timestamp and account email opt-out

Revision ID: 20260927050000
Revises: 20260927040000
Create Date: 2026-09-27 05:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260927050000"
down_revision: Union[str, None] = "20260927040000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("users", "email_notifications")
    op.drop_column("users", "terms_accepted_at")
