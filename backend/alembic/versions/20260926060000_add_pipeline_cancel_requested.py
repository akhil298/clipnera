"""Cancel flag on pipeline runs, readable by worker processes

Revision ID: 20260926060000
Revises: 20260926050000
Create Date: 2026-09-26 06:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260926060000"
down_revision: Union[str, None] = "20260926050000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_states",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("pipeline_states", "cancel_requested")
