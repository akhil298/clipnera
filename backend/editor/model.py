"""Editor projects and the log of operations that built each one's Timeline.

The Timeline is stored whole on the project (read and written with it, as
edit_engine does); every change also appends its operations to ``editor_ops``
under the version it produced, which is the project's history and undo trail.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class EditorProject(Base):
    __tablename__ = "editor_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # Bumped by every applied batch of operations; clients send the version they edited.
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Timeline v1 as JSON (editor.timeline.Timeline), defaults left out.
    timeline: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class EditorOp(Base):
    __tablename__ = "editor_ops"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_editor_ops_project_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False)
    # The project version these operations produced.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # "user", or "agent:<name>" for the in-app agent and connected agents.
    author: Mapped[str] = mapped_column(String(60), nullable=False)
    ops: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
