"""Background jobs table for the Postgres job queue

Revision ID: 20261005010000
Revises: 20261003010000
Create Date: 2026-10-05 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261005010000"
down_revision: Union[str, None] = "20261003010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_after", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_background_jobs_claim", "background_jobs", ["status", "run_after"])


def downgrade() -> None:
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs")
    op.drop_table("background_jobs")
