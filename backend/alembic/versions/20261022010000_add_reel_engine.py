"""Reel engine: premium edits on footage reels, and the registry of assets the engine made

Revision ID: 20261022010000
Revises: 20261017020000
Create Date: 2026-10-22 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261022010000"
down_revision: Union[str, None] = "20261017020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edit_projects", sa.Column("engine", sa.String(20), nullable=False, server_default="classic"))
    op.add_column("edit_projects", sa.Column("premium", sa.Text(), nullable=False, server_default="{}"))
    op.create_table(
        "reel_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False, server_default="global"),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("words", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("licence", sa.String(200), nullable=False),
        sa.Column("source", sa.String(200), nullable=False, server_default=""),
        sa.Column("made_by", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("meta", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reel_assets_kind", "reel_assets", ["kind"])
    op.create_index("ix_reel_assets_scope", "reel_assets", ["scope"])
    op.create_index("ix_reel_assets_owner_id", "reel_assets", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_reel_assets_owner_id", table_name="reel_assets")
    op.drop_index("ix_reel_assets_scope", table_name="reel_assets")
    op.drop_index("ix_reel_assets_kind", table_name="reel_assets")
    op.drop_table("reel_assets")
    op.drop_column("edit_projects", "premium")
    op.drop_column("edit_projects", "engine")
