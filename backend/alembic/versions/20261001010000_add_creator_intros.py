"""Creator channel intros, played before every export on Pro

Revision ID: 20261001010000
Revises: 20260929010000
Create Date: 2026-10-01 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261001010000"
down_revision: Union[str, None] = "20260929010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "creator_intros",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "rendering", "ready", "failed", name="creator_intro_status"),
            nullable=False, server_default="draft",
        ),
        sa.Column("platform", sa.String(length=20), nullable=False, server_default="youtube"),
        sa.Column("niche", sa.String(length=60), nullable=True),
        sa.Column("channel_name", sa.String(length=120), nullable=False),
        sa.Column("handle", sa.String(length=120), nullable=True),
        sa.Column("about", sa.Text(), nullable=False, server_default=""),
        sa.Column("tagline", sa.String(length=200), nullable=True),
        sa.Column("theme", sa.String(length=10), nullable=False, server_default="auto"),
        sa.Column("theme_used", sa.String(length=10), nullable=True),
        sa.Column("avatar_key", sa.String(length=500), nullable=True),
        sa.Column("files", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_creator_intros_user_id", "creator_intros", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_creator_intros_user_id", table_name="creator_intros")
    op.drop_table("creator_intros")
    sa.Enum(name="creator_intro_status").drop(op.get_bind(), checkfirst=True)
