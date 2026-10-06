"""Social export templates table

The model existed without a migration, so only databases built with
create_all had the table. Skipped where it already exists.

Revision ID: 20261006010000
Revises: 20261005020000
Create Date: 2026-10-06 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261006010000"
down_revision: Union[str, None] = "20261005020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("social_export_templates"):
        return
    op.create_table(
        "social_export_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("aspect_ratio", sa.String(10), nullable=False),
        sa.Column("subtitle_style", sa.String(50), nullable=True),
        sa.Column("config", sa.Text(), nullable=True),
        sa.Column("is_preset", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_social_export_templates_user_id", "social_export_templates", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_social_export_templates_user_id", table_name="social_export_templates")
    op.drop_table("social_export_templates")
