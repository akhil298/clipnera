"""add clipping pipeline tables

Revision ID: 20250904000000
Revises: 20250903180000
Create Date: 2025-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20250904000000"
down_revision: Union[str, None] = "20250903180000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'content_category') THEN CREATE TYPE content_category AS ENUM ('gaming', 'podcast_interview', 'tutorial_educational', 'vlog', 'comedy', 'reaction', 'music', 'news_politics', 'tech', 'fitness_health', 'food', 'sports', 'unknown'); END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subtitle_style_type') THEN CREATE TYPE subtitle_style_type AS ENUM ('bold_captions', 'karaoke', 'minimal', 'boxed', 'neon', 'typewriter'); END IF; END $$;"
    )

    content_category = postgresql.ENUM(
        "gaming", "podcast_interview", "tutorial_educational", "vlog",
        "comedy", "reaction", "music", "news_politics", "tech",
        "fitness_health", "food", "sports", "unknown",
        name="content_category", create_type=False
    )
    subtitle_style_type = postgresql.ENUM(
        "bold_captions", "karaoke", "minimal", "boxed", "neon", "typewriter",
        name="subtitle_style_type", create_type=False
    )

    op.create_table(
        "video_analysis",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_category", sa.String(100), nullable=True),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("topic_keywords", sa.Text, nullable=True),
        sa.Column("scene_changes", sa.Text, nullable=True),
        sa.Column("frame_descriptions", sa.Text, nullable=True),
        sa.Column("transcript_summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_video_analysis_project_id", "video_analysis", ["project_id"])

    op.create_table(
        "subtitle_styles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("style_type", subtitle_style_type, nullable=False),
        sa.Column("config", sa.Text, nullable=True),
        sa.Column("is_preset", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subtitle_styles_user_id", "subtitle_styles", ["user_id"])

    op.create_table(
        "generated_clips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("content_category", sa.String(100), nullable=True),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("s3_bucket", sa.String(255), nullable=True),
        sa.Column("presigned_url", sa.Text, nullable=True),
        sa.Column("local_path", sa.String(500), nullable=True),
        sa.Column("subtitle_style_id", sa.String(36), sa.ForeignKey("subtitle_styles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("burned_subtitle_path", sa.String(500), nullable=True),
        sa.Column("burned_presigned_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_generated_clips_project_id", "generated_clips", ["project_id"])
    op.create_index("ix_generated_clips_user_id", "generated_clips", ["user_id"])

    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'topic_research'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'visual_analysis'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'content_classification'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'highlight_detection'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'scoring'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'metadata_generation'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'subtitle_styling'"
    )
    op.execute(
        "ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'burn_in_export'"
    )


def downgrade() -> None:
    op.drop_index("ix_generated_clips_user_id", table_name="generated_clips")
    op.drop_index("ix_generated_clips_project_id", table_name="generated_clips")
    op.drop_table("generated_clips")

    op.drop_index("ix_subtitle_styles_user_id", table_name="subtitle_styles")
    op.drop_table("subtitle_styles")

    op.drop_index("ix_video_analysis_project_id", table_name="video_analysis")
    op.drop_table("video_analysis")

    op.execute("DROP TYPE IF EXISTS subtitle_style_type")
    op.execute("DROP TYPE IF EXISTS content_category")
