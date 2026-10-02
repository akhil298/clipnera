"""Store the short-form format the AI cut each clip (and each video) as

``content_format`` is one of ``formats.taxonomy.FORMATS``. Rows made before
formats existed stay null and are read as a talking head.

Revision ID: 20261002010000
Revises: 20261001020000
Create Date: 2026-10-02 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261002010000"
down_revision: Union[str, None] = "20261001020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("content_format", sa.String(length=40), nullable=True))
    op.add_column("video_analysis", sa.Column("content_format", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("video_analysis", "content_format")
    op.drop_column("generated_clips", "content_format")
