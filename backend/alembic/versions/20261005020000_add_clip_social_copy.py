"""Instagram caption and hashtags on generated clips

Revision ID: 20261005020000
Revises: 20261005010000
Create Date: 2026-10-05 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261005020000"
down_revision: Union[str, None] = "20261005010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("social_caption", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("hashtags", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "hashtags")
    op.drop_column("generated_clips", "social_caption")
