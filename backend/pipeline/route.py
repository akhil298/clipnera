from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from auth.dependencies import CurrentUserDep
from pipeline.model import PipelineStepType, StepStatus
from pipeline.service import PipelineOrchestrator
from pipeline.repository import PipelineRepository
from clip.repository import ClipRepository
from core.logging_config import get_logger
from core.database import AsyncSessionLocal
from core.exceptions import CustomException

log = get_logger(__name__)

pipeline = APIRouter(prefix="/pipeline", tags=["pipeline"])

_progress_store: dict[str, dict[str, Any]] = {}
_progress_lock = asyncio.Lock()


def _progress_callback_factory(project_id: str):
    async def callback(message: str, percent: int, _: str | None) -> None:
        async with _progress_lock:
            _progress_store[project_id] = {
                "message": message,
                "percent": percent,
                "status": "running",
            }
    return callback


async def _run_pipeline(orchestrator: PipelineOrchestrator, project_id: str, pipeline_repo: PipelineRepository) -> None:
    try:
        await orchestrator.run()
        async with _progress_lock:
            _progress_store[project_id] = {"status": "completed", "percent": 100, "message": "Pipeline completed"}
    except Exception as exc:
        log.error(f"Pipeline failed: project={project_id} error={exc}")
        async with _progress_lock:
            _progress_store[project_id] = {"status": "error", "percent": 0, "message": str(exc)}


@pipeline.post("/start/{project_id}")
async def start_pipeline(project_id: str, user: CurrentUserDep, body: dict | None = None):
    async with AsyncSessionLocal() as session:
        clip_repo = ClipRepository(session)
        pipeline_repo = PipelineRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        body = body or {}
        selected_steps = [PipelineStepType(s) for s in body.get("steps", ["download", "audio_extraction", "ai_noise_cancellation"])]
        audio_config = body.get("audio_config", {
            "ai_denoise": True,
            "noise_suppression_strength": 90,
            "de_reverb": True,
            "vocal_clarity_eq": True,
            "hum_filter": True,
        })

        await pipeline_repo.create_pipeline(project_id, selected_steps)

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user["user_id"],
            url=project.source_url or "",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=_progress_callback_factory(project_id),
        )

        asyncio.create_task(_run_pipeline(orchestrator, project_id, pipeline_repo))

        return {
            "project_id": project_id,
            "status": "started",
            "selected_steps": [s.value for s in selected_steps],
        }


@pipeline.get("/progress/{project_id}")
async def pipeline_progress(project_id: str, user: CurrentUserDep):
    async def event_stream():
        while True:
            async with _progress_lock:
                data = dict(_progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""}))
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("status") in ("completed", "error"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@pipeline.get("/status/{project_id}")
async def pipeline_status(project_id: str, user: CurrentUserDep):
    async with AsyncSessionLocal() as session:
        pipeline_repo = PipelineRepository(session)
        clip_repo = ClipRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        state = await pipeline_repo.get_pipeline(project_id)
        if not state:
            return {"project_id": project_id, "status": "not_started", "steps": []}

        logs = await pipeline_repo.get_step_logs(state.id)
        steps = []
        for log_entry in logs:
            steps.append({
                "step": log_entry.step,
                "status": log_entry.status,
                "progress_percent": log_entry.progress_percent,
                "message": log_entry.message,
                "artifact_path": log_entry.artifact_path,
                "started_at": log_entry.started_at.isoformat() if log_entry.started_at else None,
                "finished_at": log_entry.finished_at.isoformat() if log_entry.finished_at else None,
            })

        return {
            "project_id": project_id,
            "current_step": state.current_step,
            "is_completed": state.is_completed,
            "error": state.error,
            "steps": steps,
        }


@pipeline.post("/revert/{project_id}/{step}")
async def revert_step(project_id: str, step: str, user: CurrentUserDep):
    async with AsyncSessionLocal() as session:
        pipeline_repo = PipelineRepository(session)
        clip_repo = ClipRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        try:
            step_enum = PipelineStepType(step)
        except ValueError:
            raise CustomException(message=f"Invalid step: {step}", code="INVALID_STEP", status_code=400)

        state = await pipeline_repo.get_pipeline(project_id)
        if not state:
            raise CustomException(message="Pipeline not found", code="NOT_FOUND", status_code=404)

        await pipeline_repo.mark_step_reverted(state.id, step_enum)

        if step_enum == PipelineStepType.AI_NOISE_CANCELLATION:
            await pipeline_repo.save_artifact(state.id, step_enum, project.presigned_url or "")

        await pipeline_repo.update_pipeline_current_step(project_id, step_enum)

        return {"project_id": project_id, "step": step, "status": "reverted"}


@pipeline.post("/resume/{project_id}")
async def resume_pipeline(project_id: str, user: CurrentUserDep, body: dict | None = None):
    async with AsyncSessionLocal() as session:
        pipeline_repo = PipelineRepository(session)
        clip_repo = ClipRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        state = await pipeline_repo.get_pipeline(project_id)
        if not state:
            raise CustomException(message="Pipeline not found", code="NOT_FOUND", status_code=404)

        body = body or {}
        selected_steps = [PipelineStepType(s) for s in body.get("steps", ["download", "audio_extraction", "ai_noise_cancellation"])]
        audio_config = body.get("audio_config", {
            "ai_denoise": True,
            "noise_suppression_strength": 90,
            "de_reverb": True,
            "vocal_clarity_eq": True,
            "hum_filter": True,
        })

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user["user_id"],
            url=project.source_url or "",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=_progress_callback_factory(project_id),
        )

        asyncio.create_task(_run_pipeline(orchestrator, project_id, pipeline_repo))

        return {
            "project_id": project_id,
            "status": "resumed",
            "selected_steps": [s.value for s in selected_steps],
        }
