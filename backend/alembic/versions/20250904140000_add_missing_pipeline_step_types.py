"""add missing pipeline step type enum values

Revision ID: 20250904140000
Revises: 20250903180000
Create Date: 2025-09-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20250904140000"
down_revision: Union[str, None] = "20250904000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MISSING_VALUES = [
    "topic_research",
    "visual_analysis",
    "content_classification",
    "highlight_detection",
    "scoring",
    "metadata_generation",
    "subtitle_styling",
    "burn_in_export",
]


def upgrade() -> None:
    for value in MISSING_VALUES:
        op.execute(f"ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    pass
