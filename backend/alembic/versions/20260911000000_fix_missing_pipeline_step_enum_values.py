"""add missing pipeline step enum values for render and bbox steps

Revision ID: 20260911000000
Revises: 20260910000000
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260911000000"
down_revision: Union[str, None] = "20260910000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MISSING_VALUES = [
    "bounding_box_detection",
    "aspect_ratio_render",
]


def upgrade() -> None:
    for value in MISSING_VALUES:
        op.execute(f"ALTER TYPE pipeline_step_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    pass
