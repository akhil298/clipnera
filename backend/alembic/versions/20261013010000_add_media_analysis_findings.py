"""Media analyses: the step being run, and what was found, for the studio's chat

Revision ID: 20261013010000
Revises: 20261012040000
Create Date: 2026-10-13 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261013010000"
down_revision: Union[str, None] = "20261012040000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_analyses", sa.Column("stage", sa.String(20), nullable=True))
    op.add_column("media_analyses", sa.Column("findings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("media_analyses", "findings")
    op.drop_column("media_analyses", "stage")
