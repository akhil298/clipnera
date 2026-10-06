"""initial

Revision ID: 20250831120000
Revises: 
Create Date: 2025-08-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20250831120000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Each type is created once below; create_type=False stops create_table
    # from creating it a second time.
    auth_provider = postgresql.ENUM("password", "google", "microsoft", name="auth_provider", create_type=False)
    project_status = postgresql.ENUM("pending", "processing", "uploaded", "completed", "failed", name="project_status", create_type=False)
    workspace_role = postgresql.ENUM("owner", "admin", "member", "viewer", name="workspace_role", create_type=False)
    member_status = postgresql.ENUM("active", "pending", name="member_status", create_type=False)
    step_status = postgresql.ENUM("pending", "running", "completed", "failed", "reverted", "skipped", name="step_status", create_type=False)
    pipeline_step_type = postgresql.ENUM("download", "audio_extraction", "ai_noise_cancellation", "transcription", "clip_generation", "caption_styling", "auto_reframe", "export", name="pipeline_step_type", create_type=False)

    auth_provider.create(op.get_bind())
    project_status.create(op.get_bind())
    workspace_role.create(op.get_bind())
    member_status.create(op.get_bind())
    step_status.create(op.get_bind())
    pipeline_step_type.create(op.get_bind())

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("is_verified", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),

    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", auth_provider, nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),

    )
    op.create_index("ix_user_accounts_user_id", "user_accounts", ["user_id"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),

    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", workspace_role, nullable=False),
        sa.Column("status", member_status, nullable=False),
        sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),

    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    op.create_table(
        "video_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("status", project_status, nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("s3_bucket", sa.String(255), nullable=True),
        sa.Column("presigned_url", sa.Text, nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("local_path", sa.String(500), nullable=True),
        sa.Column("audio_processed_url", sa.Text, nullable=True),
        sa.Column("audio_original_url", sa.Text, nullable=True),
        sa.Column("audio_reverted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),

    )
    op.create_index("ix_video_projects_user_id", "video_projects", ["user_id"])

    op.create_table(
        "pipeline_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_step", pipeline_step_type, nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("step_artifacts", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),

    )
    op.create_index("ix_pipeline_states_project_id", "pipeline_states", ["project_id"])

    op.create_table(
        "pipeline_step_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pipeline_id", sa.String(36), sa.ForeignKey("pipeline_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step", pipeline_step_type, nullable=False),
        sa.Column("status", step_status, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("artifact_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),

    )
    op.create_index("ix_pipeline_step_logs_pipeline_id", "pipeline_step_logs", ["pipeline_id"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_step_logs_pipeline_id", table_name="pipeline_step_logs")
    op.drop_table("pipeline_step_logs")
    op.drop_index("ix_pipeline_states_project_id", table_name="pipeline_states")
    op.drop_table("pipeline_states")
    op.drop_index("ix_video_projects_user_id", table_name="video_projects")
    op.drop_table("video_projects")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_owner_id", table_name="workspaces")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_user_accounts_user_id", table_name="user_accounts")
    op.drop_table("user_accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS pipeline_step_type")
    op.execute("DROP TYPE IF EXISTS step_status")
    op.execute("DROP TYPE IF EXISTS member_status")
    op.execute("DROP TYPE IF EXISTS workspace_role")
    op.execute("DROP TYPE IF EXISTS project_status")
    op.execute("DROP TYPE IF EXISTS auth_provider")
