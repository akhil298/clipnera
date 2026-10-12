"""Edit plans: the AI director's plans and their steps

Plans proposed to the user (with the runner-up kept for a day), their status through
approval and execution, the credits held and charged, and one row per step.

Revision ID: 20261012010000
Revises: 20261009030000
Create Date: 2026-10-12 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261012010000"
down_revision: Union[str, None] = "20261009030000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "edit_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("frame", sa.Text(), nullable=False),
        sa.Column("scores", sa.Text(), nullable=False),
        sa.Column("runner_up", sa.Text(), nullable=True),
        sa.Column("runner_up_expires_at", sa.DateTime(), nullable=True),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_held", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("review_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_edit_plans_project_id", "edit_plans", ["project_id"])
    op.create_table(
        "plan_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("edit_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(60), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("intent", sa.String(80), nullable=False),
        sa.Column("why", sa.String(200), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("ops", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_after", sa.Integer(), nullable=True),
        sa.UniqueConstraint("plan_id", "step_id", name="uq_plan_steps_plan_step"),
    )
    op.create_index("ix_plan_steps_plan_id", "plan_steps", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_steps_plan_id", table_name="plan_steps")
    op.drop_table("plan_steps")
    op.drop_index("ix_edit_plans_project_id", table_name="edit_plans")
    op.drop_table("edit_plans")
