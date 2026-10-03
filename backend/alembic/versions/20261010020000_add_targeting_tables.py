"""Targeting overrides, flag segments (staff and beta seeded) and remote config

Revision ID: 20261010020000
Revises: 20261010010000
Create Date: 2026-10-10 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261010020000"
down_revision: Union[str, None] = "20261010010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_fk(name: str) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def upgrade() -> None:
    op.create_table(
        "targeting_overrides",
        sa.Column("target_kind", sa.String(16), primary_key=True),
        sa.Column("target_key", sa.String(100), primary_key=True),
        sa.Column("subject_type", sa.String(16), primary_key=True),
        sa.Column("subject_id", sa.String(36), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        _user_fk("created_by"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_targeting_overrides_subject", "targeting_overrides", ["subject_type", "subject_id"])

    op.create_table(
        "flag_segments",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_ids", postgresql.ARRAY(sa.String(36)), nullable=False, server_default="{}"),
        sa.Column("email_domains", postgresql.ARRAY(sa.String(255)), nullable=False, server_default="{}"),
        sa.Column("roles", postgresql.ARRAY(sa.String(16)), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _user_fk("updated_by"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        "INSERT INTO flag_segments (key, description, roles) VALUES "
        "('staff', 'Admins, plus the users listed here.', '{admin}'), "
        "('beta', 'People who opted in to early features.', '{}')"
    )

    op.create_table(
        "remote_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("default_value", postgresql.JSONB(), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _user_fk("updated_by"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("remote_config")
    op.drop_table("flag_segments")
    op.drop_index("ix_targeting_overrides_subject", table_name="targeting_overrides")
    op.drop_table("targeting_overrides")
