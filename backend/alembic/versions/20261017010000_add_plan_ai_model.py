"""Edit plans: the model and reasoning effort picked in the studio's AI chat

Revision ID: 20261017010000
Revises: 20261013010000
Create Date: 2026-10-17 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261017010000"
down_revision: Union[str, None] = "20261013010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edit_plans", sa.Column("ai_model", sa.String(80), nullable=True))
    op.add_column("edit_plans", sa.Column("ai_effort", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("edit_plans", "ai_effort")
    op.drop_column("edit_plans", "ai_model")
