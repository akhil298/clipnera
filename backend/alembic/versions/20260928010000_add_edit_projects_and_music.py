"""Reels edited from raw footage, and the free-licence music library

Revision ID: 20260928010000
Revises: 20260927050000
Create Date: 2026-09-28 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260928010000"
down_revision: Union[str, None] = "20260927050000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EDIT_STATUS = postgresql.ENUM("draft", "analyzing", "planned", "rendering", "done", "failed", name="edit_status", create_type=False)
MUSIC_STATUS = postgresql.ENUM("live", "pulled", name="music_status", create_type=False)


def upgrade() -> None:
    EDIT_STATUS.create(op.get_bind(), checkfirst=True)
    MUSIC_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "edit_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", EDIT_STATUS, nullable=False, server_default="draft"),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("script_mode", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("intent", sa.String(300), nullable=True),
        sa.Column("language", sa.String(20), nullable=False, server_default="en"),
        sa.Column("caption_style", sa.String(60), nullable=False, server_default="hormozi"),
        sa.Column("target_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("autopilot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sources", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("analysis", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("plan", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("timeline", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("raw_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("replans", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chat_edits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("renders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opus", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("credits_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_key", sa.String(500), nullable=True),
        sa.Column("music_credit", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_edit_projects_user_id", "edit_projects", ["user_id"])
    op.create_table(
        "music_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("artist", sa.String(300), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("licence", sa.String(40), nullable=False),
        sa.Column("licence_url", sa.String(500), nullable=False),
        sa.Column("credit_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("commercial_ok", sa.Boolean(), nullable=False),
        sa.Column("edit_ok", sa.Boolean(), nullable=False),
        sa.Column("snapshot_key", sa.String(500), nullable=False),
        sa.Column("audio_key", sa.String(500), nullable=False),
        sa.Column("audio_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("bpm", sa.Float(), nullable=True),
        sa.Column("mood", sa.String(40), nullable=False),
        sa.Column("energy", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", MUSIC_STATUS, nullable=False, server_default="live"),
        sa.Column("added_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_music_tracks_mood", "music_tracks", ["mood"])


def downgrade() -> None:
    op.drop_table("music_tracks")
    op.drop_table("edit_projects")
    MUSIC_STATUS.drop(op.get_bind(), checkfirst=True)
    EDIT_STATUS.drop(op.get_bind(), checkfirst=True)
