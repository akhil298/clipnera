"""Append-only flag audit log, with one legacy.import row per existing flag

Downgrading drops the whole change history of flags, config and segments.

Revision ID: 20261010030000
Revises: 20261010020000
Create Date: 2026-10-10 03:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261010030000"
down_revision: Union[str, None] = "20261010020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flag_audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column("target_key", sa.String(100), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=True),
        sa.Column("subject_id", sa.String(36), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
    )
    op.create_index("ix_flag_audit_log_target", "flag_audit_log", ["target_key", "id"])
    op.execute(
        "CREATE OR REPLACE FUNCTION flag_audit_log_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'flag_audit_log is append-only'; END $$"
    )
    op.execute(
        "CREATE TRIGGER flag_audit_log_append_only BEFORE UPDATE OR DELETE ON flag_audit_log "
        "FOR EACH ROW EXECUTE FUNCTION flag_audit_log_reject_change()"
    )
    # History starts complete: the state every existing flag had when the log began.
    op.execute(
        "INSERT INTO flag_audit_log (actor_id, action, target_kind, target_key, after, reason) "
        "SELECT updated_by, 'legacy.import', 'flag', key, "
        "jsonb_build_object('enabled', enabled, 'rollout_bps', rollout_bps, 'rules', rules, "
        "'bucket_salt', bucket_salt, 'killed', killed, 'killed_reason', killed_reason, 'version', version), "
        "'State when the audit log was created' FROM feature_flags ORDER BY key"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS flag_audit_log_append_only ON flag_audit_log")
    op.execute("DROP FUNCTION IF EXISTS flag_audit_log_reject_change()")
    op.drop_index("ix_flag_audit_log_target", table_name="flag_audit_log")
    op.drop_table("flag_audit_log")
