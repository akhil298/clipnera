"""AI usage by editor role

Records which AI-editor role (router, director, critic...) each call was made
for, so spend can be read back per role and per provider. Null for the
pipeline's calls, which are attributed by step.

Revision ID: 20261009010000
Revises: 20261007020000
Create Date: 2026-10-09 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261009010000"
down_revision: Union[str, None] = "20261007020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_usage", sa.Column("role", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_usage", "role")
