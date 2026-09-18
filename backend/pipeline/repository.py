from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc
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

    async def get_step_logs(self, pipeline_id: str) -> list[PipelineStepLog]:
        stmt = (
            select(PipelineStepLog)
            .where(PipelineStepLog.pipeline_id == pipeline_id)
            .order_by(PipelineStepLog.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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

    async def mark_step_reverted(self, pipeline_id: str, step: PipelineStepType, artifact_path: str | None = None) -> None:
        await self.update_step_status(
            pipeline_id,
            step,
            StepStatus.REVERTED,
            artifact_path=artifact_path,
            message="Reverted to previous state",
        )

    async def update_pipeline_current_step(self, project_id: str, current_step: PipelineStepType, is_completed: bool = False) -> None:
        stmt = select(PipelineState).where(PipelineState.project_id == project_id)
        result = await self._session.execute(stmt)
        state = result.scalar_one_or_none()
        if state:
            state.current_step = current_step.value
            state.is_completed = is_completed
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
