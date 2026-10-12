"""Editor history: undo, redo and who touched what

Each batch in the editor's op log now keeps the ops that undo it, which
fields of which items it changed, whether it was an edit or an undo/redo,
and the agent step and turn that made it.

Revision ID: 20261009020000
Revises: 20261009010000
Create Date: 2026-10-09 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261009020000"
down_revision: Union[str, None] = "20261009010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("editor_ops", sa.Column("kind", sa.String(10), nullable=False, server_default="edit"))
    op.add_column("editor_ops", sa.Column("targets", sa.Text(), nullable=True))
    op.add_column("editor_ops", sa.Column("step_id", sa.String(60), nullable=True))
    op.add_column("editor_ops", sa.Column("turn_id", sa.String(60), nullable=True))
    op.add_column("editor_ops", sa.Column("inverse", sa.Text(), nullable=True))
    op.add_column("editor_ops", sa.Column("touched", sa.Text(), nullable=True))
    op.create_index("ix_editor_ops_step_id", "editor_ops", ["step_id"])


def downgrade() -> None:
    op.drop_index("ix_editor_ops_step_id", table_name="editor_ops")
    for column in ("touched", "inverse", "turn_id", "step_id", "targets", "kind"):
        op.drop_column("editor_ops", column)
