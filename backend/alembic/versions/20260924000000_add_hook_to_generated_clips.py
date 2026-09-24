"""add hook span to generated_clips

Revision ID: 20260924000000
Revises: 20260911003000
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260924000000"
down_revision: Union[str, None] = "20260911003000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("hook_start", sa.Float(), nullable=True))
    op.add_column("generated_clips", sa.Column("hook_end", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "hook_end")
    op.drop_column("generated_clips", "hook_start")
