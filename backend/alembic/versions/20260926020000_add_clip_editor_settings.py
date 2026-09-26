"""Store each clip's editor settings

Revision ID: 20260926020000
Revises: 20260926010000
Create Date: 2026-09-26 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260926020000"
down_revision: Union[str, None] = "20260926010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("editor_settings", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "editor_settings")
