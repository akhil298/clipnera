from __future__ import annotations

import json
from typing import Awaitable, Callable, Optional
from uuid import uuid4

from clip_generation.model import GeneratedClip
from clip_generation.repository import ClipRepository
from clip_generation.service import clip_source
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from depth_captions.pipeline import create_depth_captions_job
from depth_captions.schema import (
    STYLE_PRESETS,
    DepthCaptionJobResponse,
    DepthCaptionJobStatus,
    DepthCaptionRequest,
    DepthCaptionsJobStatusResponse,
    DepthCaptionsRenderRequest,
    DepthMode,
    StylePreset,
    TranscriptSegment,
)

log = get_logger(__name__)

# In-memory job storage (in production, use Redis or database)
_job_store: dict[str, DepthCaptionJobResponse] = {}

Scheduler = Callable[[Callable[[], Awaitable[None]]], None]


def _transcript_segments(clip: GeneratedClip) -> list[TranscriptSegment]:
    if not clip.transcript:
        return []
    try:
        transcript_data = json.loads(clip.transcript)
    except json.JSONDecodeError:
        return []
    return [
        TranscriptSegment(
            start=seg.get("start", 0),
            end=seg.get("end", 0),
            text=seg.get("text", ""),
            speaker=seg.get("speaker"),
            words=seg.get("words", []),
        )
        for seg in transcript_data
    ]


def _status_response(job: DepthCaptionJobResponse) -> DepthCaptionsJobStatusResponse:
    return DepthCaptionsJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        preview_url=job.preview_url,
        output_url=job.output_url,
        error=job.error,
    )


def _get_job(job_id: str) -> DepthCaptionJobResponse:
    if job_id not in _job_store:
        raise CustomException(message="Job not found", code="NOT_FOUND", status_code=404)
    return _job_store[job_id]


class DepthCaptionsService:
    async def start_render(
        self, request: DepthCaptionsRenderRequest, user_id: str, schedule: Scheduler
    ) -> DepthCaptionJobResponse:
        """Queue a depth captions render of a clip the caller owns; ``schedule``
        runs the job after the response is sent."""
        async with AsyncSessionLocal() as session:
            clip = await ClipRepository(session).get_clip(request.clip_id, user_id)
            if not clip:
                raise CustomException(message="Clip not found", code="NOT_FOUND", status_code=404)
            if clip.project_id != request.project_id:
                raise CustomException(message="Clip does not belong to project", code="FORBIDDEN", status_code=403)
            if not clip.s3_key and not clip.local_path:
                raise CustomException(message="Clip video file not available", code="CLIP_UNAVAILABLE", status_code=400)
            segments = _transcript_segments(clip)

        job_id = str(uuid4())
        job_response = DepthCaptionJobResponse(
            job_id=job_id,
            status=DepthCaptionJobStatus.QUEUED,
            progress=0,
            stage="queued",
        )
        _job_store[job_id] = job_response

        dc_request = DepthCaptionRequest(
            project_id=request.project_id,
            clip_id=request.clip_id,
            style=request.style,
            depth_mode=request.depth_mode,
            language=request.language,
        )

        async def run_job() -> None:
            await self._run_job(job_id, dc_request, segments, clip)

        schedule(run_job)
        return job_response

    @staticmethod
    async def _run_job(
        job_id: str, dc_request: DepthCaptionRequest, segments: list[TranscriptSegment], clip: GeneratedClip
    ) -> None:
        try:
            _job_store[job_id] = DepthCaptionJobResponse(
                job_id=job_id,
                status=DepthCaptionJobStatus.PREPARING,
                progress=5,
                stage="preparing",
            )

            async def progress_cb(message: str, percent: int, stage: Optional[str] = None):
                _job_store[job_id] = DepthCaptionJobResponse(
                    job_id=job_id,
                    status=DepthCaptionJobStatus(stage) if stage else DepthCaptionJobStatus.ANALYZING,
                    progress=percent,
                    stage=stage or "processing",
                )

            async with clip_source(clip) as clip_path:
                result = await create_depth_captions_job(
                    dc_request,
                    segments,
                    clip_path,
                    progress_callback=progress_cb,
                )
            _job_store[job_id] = result

        except Exception as e:
            log.exception(f"Depth captions job {job_id} failed")
            _job_store[job_id] = DepthCaptionJobResponse(
                job_id=job_id,
                status=DepthCaptionJobStatus.FAILED,
                progress=0,
                stage="failed",
                error=str(e),
                retryable=True,
            )

    @staticmethod
    def get_job_status(job_id: str) -> DepthCaptionsJobStatusResponse:
        return _status_response(_get_job(job_id))

    @staticmethod
    def list_jobs() -> list[DepthCaptionsJobStatusResponse]:
        return [_status_response(job) for job in _job_store.values()]

    @staticmethod
    def cancel_job(job_id: str) -> dict:
        job = _get_job(job_id)
        if job.status in [DepthCaptionJobStatus.COMPLETED, DepthCaptionJobStatus.FAILED]:
            raise CustomException(message="Job already completed", code="JOB_COMPLETED", status_code=400)

        # In production, actually cancel the background task
        _job_store[job_id] = DepthCaptionJobResponse(
            job_id=job_id,
            status=DepthCaptionJobStatus.FAILED,
            progress=job.progress,
            stage="cancelled",
            error="Job cancelled by user",
        )
        return {"message": "Job cancelled"}

    @staticmethod
    def list_styles() -> dict:
        styles = []
        for preset in StylePreset:
            config = STYLE_PRESETS.get(preset)
            if config:
                styles.append({
                    "id": preset.value,
                    "name": preset.value.replace("_", " ").title(),
                    "config": config.model_dump(),
                })
        return {"styles": styles}

    @staticmethod
    def list_depth_modes() -> dict:
        return {
            "modes": [
                {"id": mode.value, "name": mode.value.replace("_", " ").title()}
                for mode in DepthMode
            ]
        }
