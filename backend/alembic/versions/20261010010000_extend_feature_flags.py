"""Extend feature_flags for targeting and kills; add the flag_state version row

Server defaults keep every existing row's meaning: rollout 100%, no rules, not
killed, so a flag that was on stays on for everyone.

Revision ID: 20261010010000
Revises: 20261007020000
Create Date: 2026-10-10 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261010010000"
down_revision: Union[str, None] = "20261007020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("feature_flags", sa.Column("rollout_bps", sa.Integer(), nullable=False, server_default="10000"))
    op.add_column(
        "feature_flags", sa.Column("rules", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb"))
    )
    op.add_column("feature_flags", sa.Column("bucket_salt", sa.String(100), nullable=True))
    op.add_column("feature_flags", sa.Column("killed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("feature_flags", sa.Column("killed_reason", sa.Text(), nullable=True))
    op.add_column(
        "feature_flags",
        sa.Column("killed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("feature_flags", sa.Column("killed_at", sa.DateTime(), nullable=True))
    op.add_column("feature_flags", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_feature_flags_rollout_bps", "feature_flags", "rollout_bps BETWEEN 0 AND 10000")

    op.create_table(
        "flag_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
    )
    op.execute("INSERT INTO flag_state (id, version) VALUES (1, 1)")


def downgrade() -> None:
    op.drop_table("flag_state")
    op.drop_constraint("ck_feature_flags_rollout_bps", "feature_flags", type_="check")
    for column in ("version", "killed_at", "killed_by", "killed_reason", "killed", "bucket_salt", "rules", "rollout_bps"):
        op.drop_column("feature_flags", column)
