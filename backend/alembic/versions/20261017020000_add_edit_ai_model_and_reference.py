"""Footage reels: the picked AI model and effort, and a reference reel's link

Revision ID: 20261017020000
Revises: 20261017010000
Create Date: 2026-10-17 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261017020000"
down_revision: Union[str, None] = "20261017010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edit_projects", sa.Column("ai_model", sa.String(80), nullable=True))
    op.add_column("edit_projects", sa.Column("ai_effort", sa.String(10), nullable=True))
    op.add_column("edit_projects", sa.Column("reference_url", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("edit_projects", "reference_url")
    op.drop_column("edit_projects", "ai_effort")
    op.drop_column("edit_projects", "ai_model")
