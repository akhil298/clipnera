"""Clip feedback events and director versioning

Revision ID: 20260926050000
Revises: 20260926040000
Create Date: 2026-09-26 05:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260926050000"
down_revision: Union[str, None] = "20260926040000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_clips", sa.Column("director_version", sa.String(40), nullable=True))
    op.create_table(
        "clip_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "clip_id", sa.String(36), sa.ForeignKey("generated_clips.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clip_events_clip_kind", "clip_events", ["clip_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_clip_events_clip_kind", table_name="clip_events")
    op.drop_table("clip_events")
    op.drop_column("generated_clips", "director_version")
