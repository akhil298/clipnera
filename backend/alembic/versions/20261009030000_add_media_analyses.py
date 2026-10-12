"""Media analyses: the AI editor's understanding of each project asset

One row per editor project asset with the state of its Media Understanding
Document and the S3 key it is stored under.

Revision ID: 20261009030000
Revises: 20261009020000
Create Date: 2026-10-09 03:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261009030000"
down_revision: Union[str, None] = "20261009020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(40), nullable=False),
        sa.Column("asset_key", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("mud_key", sa.String(500), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "asset_id", name="uq_media_analyses_project_asset"),
    )
    op.create_index("ix_media_analyses_project_id", "media_analyses", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_media_analyses_project_id", table_name="media_analyses")
    op.drop_table("media_analyses")
