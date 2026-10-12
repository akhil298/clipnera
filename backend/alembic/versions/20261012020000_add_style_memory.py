"""Style memory: what the AI editor learns from a user's corrections

style_profiles holds one row of beliefs per user; style_events the corrections they came from.

Revision ID: 20261012020000
Revises: 20261012010000
Create Date: 2026-10-12 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261012020000"
down_revision: Union[str, None] = "20261012010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "style_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("beliefs", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "style_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_style_events_user_id", "style_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_style_events_user_id", table_name="style_events")
    op.drop_table("style_events")
    op.drop_table("style_profiles")
