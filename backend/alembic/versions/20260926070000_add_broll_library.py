"""B-roll library: assets, licences and usage

Revision ID: 20260926070000
Revises: 20260926060000
Create Date: 2026-09-26 07:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260926070000"
down_revision: Union[str, None] = "20260926060000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ASSET_KIND = postgresql.ENUM("stock", "template", "generated", "user", name="broll_asset_kind", create_type=False)
ASSET_STATUS = postgresql.ENUM(
    "ingesting", "live", "blocked", "taken_down", "failed", name="broll_asset_status", create_type=False,
)


def upgrade() -> None:
    ASSET_KIND.create(op.get_bind(), checkfirst=True)
    ASSET_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "broll_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", ASSET_KIND, nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("shot_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False, server_default=""),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", postgresql.ARRAY(sa.String(80)), nullable=False, server_default="{}"),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orientation", sa.String(10), nullable=False, server_default="landscape"),
        sa.Column("fps", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("has_people", sa.Boolean(), nullable=True),
        sa.Column("has_logos", sa.Boolean(), nullable=True),
        sa.Column("status", ASSET_STATUS, nullable=False, server_default="ingesting"),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("vertical_key", sa.String(500), nullable=True),
        sa.Column("proxy_key", sa.String(500), nullable=True),
        sa.Column("thumb_key", sa.String(500), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source", "source_id", "shot_index", name="uq_broll_assets_source_shot"),
    )
    op.create_index("ix_broll_assets_owner_user_id", "broll_assets", ["owner_user_id"])
    op.create_index("ix_broll_assets_content_hash", "broll_assets", ["content_hash"])
    op.create_index("ix_broll_assets_status_orientation", "broll_assets", ["status", "orientation"])
    op.create_index(
        "ix_broll_assets_search", "broll_assets", [sa.text("to_tsvector('english', search_text)")],
        postgresql_using="gin",
    )
    op.create_table(
        "broll_licenses",
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("broll_assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("license_code", sa.String(40), nullable=False),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("author", sa.String(300), nullable=True),
        sa.Column("author_url", sa.Text(), nullable=True),
        sa.Column("attribution_text", sa.Text(), nullable=True),
        sa.Column("commercial_ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_record_key", sa.String(500), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "broll_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("broll_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scene_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("picked_rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("swapped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_broll_usage_asset_id", "broll_usage", ["asset_id"])
    op.create_index("ix_broll_usage_user_id", "broll_usage", ["user_id"])


def downgrade() -> None:
    op.drop_table("broll_usage")
    op.drop_table("broll_licenses")
    op.drop_table("broll_assets")
    ASSET_STATUS.drop(op.get_bind(), checkfirst=True)
    ASSET_KIND.drop(op.get_bind(), checkfirst=True)
