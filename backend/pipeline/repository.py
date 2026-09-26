from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.service import PipelineOrchestrator
from pipeline.model import PipelineState, PipelineStepLog, PipelineStepType, StepStatus
from clip.repository import ClipRepository
from core.logging_config import get_logger
from core.database import AsyncSessionLocal

log = get_logger(__name__)


class PipelineRepository:
    def __init__(self, session) -> None:
        self._session = session

    async def create_pipeline(self, project_id: str, steps: list[PipelineStepType]) -> PipelineState:
        state = PipelineState(
            project_id=project_id,
            current_step=steps[0].value if steps else PipelineStepType.DOWNLOAD.value,
            is_completed=False,
            step_artifacts="{}",
        )
        self._session.add(state)
        await self._session.commit()
        await self._session.refresh(state)

        for step in steps:
            log_entry = PipelineStepLog(
                pipeline_id=state.id,
                step=step.value,
                status=StepStatus.PENDING.value,
            )
            self._session.add(log_entry)
        await self._session.commit()
        return state

    async def get_pipeline(self, project_id: str) -> PipelineState | None:
        """Return the most recent pipeline state for a project.

        create_pipeline() inserts a new row per /start, so a restarted project has
        several. scalar_one_or_none() raised MultipleResultsFound on those, which
        made every status read — including the one reporting a failure — blow up.
        """
        stmt = (
            select(PipelineState)
            .where(PipelineState.project_id == project_id)
            .order_by(desc(PipelineState.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def set_cancel_requested(self, project_id: str, requested: bool) -> bool:
        """Flag the project's latest run; False when it has no run."""
        state = await self.get_pipeline(project_id)
        if not state:
            return False
        state.cancel_requested = requested
        await self._session.commit()
        return True

    async def is_cancel_requested(self, project_id: str) -> bool:
        state = await self.get_pipeline(project_id)
        return bool(state and state.cancel_requested)

    async def get_step_logs(self, pipeline_id: str) -> list[PipelineStepLog]:
        stmt = (
            select(PipelineStepLog)
            .where(PipelineStepLog.pipeline_id == pipeline_id)
            .order_by(PipelineStepLog.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_pipelines(self, project_ids: list[str]) -> dict[str, PipelineState]:
        """Most recent PipelineState for each project, in one query.

        The dashboard used to call get_pipeline() once per project, which turned a
        project list into N round trips and saturated the connection pool.
        """
        if not project_ids:
            return {}
        stmt = (
            select(PipelineState)
            .where(PipelineState.project_id.in_(project_ids))
            .order_by(PipelineState.project_id, desc(PipelineState.created_at))
        )
        result = await self._session.execute(stmt)
        latest: dict[str, PipelineState] = {}
        for state in result.scalars().all():
            # Ordered newest-first per project, so the first row wins.
            latest.setdefault(state.project_id, state)
        return latest

    async def get_step_logs_for_pipelines(
        self, pipeline_ids: list[str]
    ) -> dict[str, list[PipelineStepLog]]:
        """Step logs for several pipelines at once, grouped by pipeline id."""
        if not pipeline_ids:
            return {}
        stmt = (
            select(PipelineStepLog)
            .where(PipelineStepLog.pipeline_id.in_(pipeline_ids))
            .order_by(PipelineStepLog.created_at.asc())
        )
        result = await self._session.execute(stmt)
        grouped: dict[str, list[PipelineStepLog]] = {}
        for entry in result.scalars().all():
            grouped.setdefault(entry.pipeline_id, []).append(entry)
        return grouped

    async def get_step_logs_for_pipeline(self, project_id: str) -> list[PipelineStepLog]:
        stmt = (
            select(PipelineStepLog)
            .join(PipelineState, PipelineStepLog.pipeline_id == PipelineState.id)
            .where(PipelineState.project_id == project_id)
            .order_by(PipelineStepLog.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_step_status(
        self, pipeline_id: str, step: PipelineStepType, status: StepStatus, **kwargs
    ) -> PipelineStepLog | None:
        stmt = select(PipelineStepLog).where(
            PipelineStepLog.pipeline_id == pipeline_id,
            PipelineStepLog.step == step.value,
        )
        result = await self._session.execute(stmt)
        log_entry = result.scalar_one_or_none()
        if not log_entry:
            return None
        log_entry.status = status.value
        if "progress_percent" in kwargs:
            log_entry.progress_percent = kwargs["progress_percent"]
        if "message" in kwargs:
            log_entry.message = kwargs["message"]
        if "artifact_path" in kwargs:
            log_entry.artifact_path = kwargs["artifact_path"]
        if status == StepStatus.RUNNING:
            log_entry.started_at = datetime.utcnow()
        if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.REVERTED):
            log_entry.finished_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(log_entry)
        return log_entry

    async def fail_running_steps(self, pipeline_ids: list[str], message: str) -> None:
        """Close out steps a dead run left RUNNING, so none spins forever in the UI."""
        if not pipeline_ids:
            return
        await self._session.execute(
            update(PipelineStepLog)
            .where(
                PipelineStepLog.pipeline_id.in_(pipeline_ids),
                PipelineStepLog.status == StepStatus.RUNNING.value,
            )
            .values(status=StepStatus.FAILED.value, message=message, finished_at=datetime.utcnow())
        )

    async def fail_unfinished_pipelines(self, error: str) -> list[str]:
        """Mark every run with no outcome as failed; return the affected project ids.

        Only for startup: runs live in this process's memory, so any run still
        open when the process starts belonged to a process that is gone.
        """
        result = await self._session.execute(
            select(PipelineState).where(
                PipelineState.is_completed.is_(False),
                PipelineState.error.is_(None),
            )
        )
        states = result.scalars().all()
        for state in states:
            state.error = error
        await self.fail_running_steps([s.id for s in states], error)
        await self._session.commit()

        # A project can have older, superseded runs; only fail the project when
        # its newest run is one of the interrupted ones.
        interrupted = {s.id for s in states}
        latest = await self.get_latest_pipelines(list({s.project_id for s in states}))
        return [pid for pid, state in latest.items() if state.id in interrupted]

    async def mark_step_reverted(self, pipeline_id: str, step: PipelineStepType, artifact_path: str | None = None) -> None:
        await self.update_step_status(
            pipeline_id,
            step,
            StepStatus.REVERTED,
            artifact_path=artifact_path,
            message="Reverted to previous state",
        )

    async def update_pipeline_current_step(self, project_id: str, current_step: PipelineStepType, is_completed: bool = False) -> None:
        """Advance the newest pipeline for a project.

        A restarted project has several pipeline rows, and scalar_one_or_none()
        raised MultipleResultsFound on those — which meant the run that raised it
        was never marked completed and the UI showed it as processing forever.
        """
        state = await self.get_pipeline(project_id)
        if state:
            state.current_step = current_step.value
            state.is_completed = is_completed
            await self._session.commit()

    async def update_step_progress(
        self,
        project_id: str,
        step: PipelineStepType,
        progress_percent: int,
        message: str | None = None,
    ) -> None:
        """Record how far through a step the run is, for the polled /status view.

        Kept separate from update_step_status() so a progress tick can never
        change a step's status, and so it can no-op quietly when the step row is
        missing rather than failing the run.
        """
        state = await self.get_pipeline(project_id)
        if not state:
            return
        stmt = select(PipelineStepLog).where(
            PipelineStepLog.pipeline_id == state.id,
            PipelineStepLog.step == step.value,
        )
        result = await self._session.execute(stmt)
        log_entry = result.scalars().first()
        if not log_entry:
            return
        log_entry.progress_percent = progress_percent
        if message:
            log_entry.message = message
        await self._session.commit()

    async def save_artifact(self, pipeline_id: str, step: PipelineStepType, artifact_path: str) -> None:
        stmt = select(PipelineStepLog).where(
            PipelineStepLog.pipeline_id == pipeline_id,
            PipelineStepLog.step == step.value,
        )
        result = await self._session.execute(stmt)
        log_entry = result.scalar_one_or_none()
        if log_entry:
            log_entry.artifact_path = artifact_path
            await self._session.commit()


class PipelineService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = PipelineRepository(session)

    async def start_pipeline(self, project_id: str, user_id: str, selected_steps: list[PipelineStepType], audio_config: dict) -> dict:
        state = await self._repo.create_pipeline(project_id, selected_steps)

        async def progress_callback(message: str, percent: int, _: str | None) -> None:
            pass

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user_id,
            url="",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=progress_callback,
            resume=False,
        )

        asyncio.create_task(self._run_pipeline(orchestrator, project_id))

        return {"pipeline_id": state.id, "status": "started"}

    async def _run_pipeline(self, orchestrator: PipelineOrchestrator, project_id: str) -> None:
        try:
            await orchestrator.run()
        except Exception as exc:
            log.error(f"Pipeline failed: project={project_id} error={exc}")
