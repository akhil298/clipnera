"""add poster_url to generated_clips

Revision ID: 20260911003000
Revises: 20260911000000
Create Date: 2026-09-11 00:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260911003000"
down_revision: Union[str, None] = "20260911000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("poster_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "poster_url")
