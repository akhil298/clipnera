from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260910000000"
down_revision: Union[str, None] = "20250905150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'bounding_box_detection'")
    op.execute("ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS 'aspect_ratio_render'")

    op.add_column("video_analysis", sa.Column("analysis_json", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("scores", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("transcript", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("visual_analysis", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("bounding_boxes", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("crop_tracking", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("output_formats", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("output_files", sa.Text(), nullable=True))
    op.add_column("generated_clips", sa.Column("analysis_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_clips", "analysis_json")
    op.drop_column("generated_clips", "output_files")
    op.drop_column("generated_clips", "output_formats")
    op.drop_column("generated_clips", "crop_tracking")
    op.drop_column("generated_clips", "bounding_boxes")
    op.drop_column("generated_clips", "visual_analysis")
    op.drop_column("generated_clips", "scores")
    op.drop_column("generated_clips", "transcript")
    op.drop_column("video_analysis", "analysis_json")
