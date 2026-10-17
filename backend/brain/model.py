"""Plans the director proposed, and their steps as the user sees and runs them (TODO 10.1.1)."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PlanStatus:
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"
    STOPPED = "stopped"


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class EditPlan(Base):
    __tablename__ = "edit_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=PlanStatus.PROPOSED)
    # The project version the plan was made against; execution re-solves against the head anyway.
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # PlanIR, IntentFrame and the scorer's summary, as JSON.
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    frame: Mapped[str] = mapped_column(Text, nullable=False)
    scores: Mapped[str] = mapped_column(Text, nullable=False)
    # The runner-up, kept for "try the other version" until it expires (9.4.4).
    runner_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    runner_up_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Credits held at send/approve and charged so far (Phase 14).
    credits_held: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credits_charged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Critic review rounds run (Phase 13) and the verifier's last findings.
    review_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The model and effort picked in the chat when the plan was made; running it uses them too.
    ai_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_effort: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class PlanStepRow(Base):
    __tablename__ = "plan_steps"
    __table_args__ = (UniqueConstraint("plan_id", "step_id", name="uq_plan_steps_plan_step"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("edit_plans.id", ondelete="CASCADE"), nullable=False,
                                         index=True)
    # The PlanIR step id; also the op log's step_id, so "undo this step" undoes exactly it.
    step_id: Mapped[str] = mapped_column(String(60), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    intent: Mapped[str] = mapped_column(String(80), nullable=False)
    why: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=StepStatus.PENDING)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version_after: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StyleProfile(Base):
    """What the AI has learned about one user's taste (BLUEPRINT §3B.8): beliefs by style key, as JSON."""

    __tablename__ = "style_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
                                         unique=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    beliefs: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class StyleEvent(Base):
    """One preference the user showed by correcting the AI, kept so beliefs can be explained and rebuilt."""

    __tablename__ = "style_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
                                         index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class EditorRender(Base):
    """A full-quality render of an editor project on the server (TODO 17.2)."""

    __tablename__ = "editor_renders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # The project version rendered.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # queued | rendering | done | failed
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(80), nullable=False, default="Waiting to start")
    key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
