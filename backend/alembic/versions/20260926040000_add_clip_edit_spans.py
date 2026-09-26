"""Stitched clip bodies: the source spans a clip is cut from

Revision ID: 20260926040000
Revises: 20260926030000
Create Date: 2026-09-26 04:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260926040000"
down_revision: Union[str, None] = "20260926030000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("edit_spans", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "edit_spans")
