"""add brand_kits table

Revision ID: 20250903180000
Revises: 20250831120000
Create Date: 2025-09-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20250903180000"
down_revision: Union[str, None] = "20250831120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'caption_preset') THEN CREATE TYPE caption_preset AS ENUM ('hormozi', 'mrbeast', 'neon', 'cyberpunk', 'minimal', 'karaoke_yellow', 'sunset'); END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'logo_position') THEN CREATE TYPE logo_position AS ENUM ('top_left', 'top_right', 'bottom_left', 'bottom_right'); END IF; END $$;"
    )

    caption_preset = postgresql.ENUM(
        "hormozi", "mrbeast", "neon", "cyberpunk", "minimal", "karaoke_yellow", "sunset",
        name="caption_preset", create_type=False
    )
    logo_position = postgresql.ENUM(
        "top_left", "top_right", "bottom_left", "bottom_right",
        name="logo_position", create_type=False
    )

    op.create_table(
        "brand_kits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("brand_name", sa.String(255), nullable=False),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("logo_position", logo_position, nullable=False),
        sa.Column("logo_opacity", sa.Integer(), nullable=False),
        sa.Column("logo_size", sa.Integer(), nullable=False),
        sa.Column("primary_color", sa.String(9), nullable=False),
        sa.Column("secondary_color", sa.String(9), nullable=False),
        sa.Column("preferred_font", sa.String(100), nullable=False),
        sa.Column("default_preset", caption_preset, nullable=False),
        sa.Column("auto_emojis", sa.Boolean(), nullable=False),
        sa.Column("outro_cta_text", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_brand_kits_user_id", "brand_kits", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_brand_kits_user_id", table_name="brand_kits")
    op.drop_table("brand_kits")
    op.execute("DROP TYPE IF EXISTS logo_position")
    op.execute("DROP TYPE IF EXISTS caption_preset")
