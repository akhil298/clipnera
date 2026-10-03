"""Admin permissions for flags; every existing admin gets all five

Revision ID: 20261010040000
Revises: 20261010030000
Create Date: 2026-10-10 04:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261010040000"
down_revision: Union[str, None] = "20261010030000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS = ("flags.view", "flags.kill", "flags.edit", "config.edit", "segments.edit")


def upgrade() -> None:
    op.create_table(
        "admin_permissions",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(32), primary_key=True),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    values = ", ".join(f"('{permission}')" for permission in PERMISSIONS)
    op.execute(
        "INSERT INTO admin_permissions (user_id, permission) "
        f"SELECT users.id, p.permission FROM users CROSS JOIN (VALUES {values}) AS p(permission) "
        "WHERE users.role = 'admin'"
    )


def downgrade() -> None:
    op.drop_table("admin_permissions")
