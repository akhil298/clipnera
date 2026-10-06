"""Rename enum types to the names the models use

The initial migration named four types with underscores (workspace_role)
while the models' Enum columns use SQLAlchemy's default names
(workspacerole). Databases built with create_all already have the model
names; ones built from migrations failed every insert into these columns
with 'type "workspacerole" does not exist'. Renames only where needed.

Revision ID: 20261006020000
Revises: 20261006010000
Create Date: 2026-10-06 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261006020000"
down_revision: Union[str, None] = "20261006010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# migration name -> model name
RENAMES = {
    "workspace_role": "workspacerole",
    "member_status": "memberstatus",
    "project_status": "projectstatus",
    "step_status": "stepstatus",
}


def _rename(old: str, new: str) -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = '{old}')
               AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{new}') THEN
                ALTER TYPE {old} RENAME TO {new};
            END IF;
        END $$;
    """)


def upgrade() -> None:
    for old, new in RENAMES.items():
        _rename(old, new)


def downgrade() -> None:
    for old, new in RENAMES.items():
        _rename(new, old)
