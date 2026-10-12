"""Editor renders: full-quality server renders of editor projects

Revision ID: 20261012030000
Revises: 20261012020000
Create Date: 2026-10-12 03:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261012030000"
down_revision: Union[str, None] = "20261012020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "editor_renders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("key", sa.String(500), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_editor_renders_project_id", "editor_renders", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_editor_renders_project_id", table_name="editor_renders")
    op.drop_table("editor_renders")
