"""Several reels from one premium edit: the list of every reel cut from the footage

Revision ID: 20261023020000
Revises: 20261023010000
Create Date: 2026-10-23 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261023020000"
down_revision: Union[str, None] = "20261023010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edit_projects", sa.Column("reels", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("edit_projects", "reels")
