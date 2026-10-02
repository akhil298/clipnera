"""Editor projects (Timeline v1) and their operation log

Revision ID: 20261003010000
Revises: 20261001020000
Create Date: 2026-10-03 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261003010000"
down_revision: Union[str, None] = "20261001020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "editor_projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeline", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_editor_projects_user_id", "editor_projects", ["user_id"])
    op.create_table(
        "editor_ops",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=60), nullable=False),
        sa.Column("ops", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "version", name="uq_editor_ops_project_version"),
    )


def downgrade() -> None:
    op.drop_table("editor_ops")
    op.drop_index("ix_editor_projects_user_id", table_name="editor_projects")
    op.drop_table("editor_projects")
