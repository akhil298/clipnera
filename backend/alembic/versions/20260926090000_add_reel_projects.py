"""Reels built from images, a script and B-roll

Revision ID: 20260926090000
Revises: 20260926080000
Create Date: 2026-09-26 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260926090000"
down_revision: Union[str, None] = "20260926080000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REEL_STATUS = postgresql.ENUM("draft", "planning", "ready", "rendering", "done", "failed", name="reel_status", create_type=False)


def upgrade() -> None:
    REEL_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "reel_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", REEL_STATUS, nullable=False, server_default="draft"),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("style", sa.String(40), nullable=False, server_default="clean"),
        sa.Column("images", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("voiceover_key", sa.String(500), nullable=True),
        sa.Column("words", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("scenes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("duration_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("output_key", sa.String(500), nullable=True),
        sa.Column("credits_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reel_projects_user_id", "reel_projects", ["user_id"])


def downgrade() -> None:
    op.drop_table("reel_projects")
    REEL_STATUS.drop(op.get_bind(), checkfirst=True)
