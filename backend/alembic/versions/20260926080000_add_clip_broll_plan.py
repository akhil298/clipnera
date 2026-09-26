"""B-roll cutaway plan on generated clips

Revision ID: 20260926080000
Revises: 20260926070000
Create Date: 2026-09-26 08:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260926080000"
down_revision: Union[str, None] = "20260926070000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("broll_plan", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "broll_plan")
