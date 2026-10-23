"""Footage reels from a YouTube link: the video to edit, fetched as footage when the edit starts

Revision ID: 20261023010000
Revises: 20261022010000
Create Date: 2026-10-23 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261023010000"
down_revision: Union[str, None] = "20261022010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edit_projects", sa.Column("source_url", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("edit_projects", "source_url")
