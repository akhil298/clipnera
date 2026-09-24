from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Any
from uuid import uuid4
import asyncio

from auth.dependencies import CurrentUserDep
from core.logging_config import get_logger
from core.exceptions import CustomException
from depth_captions.schema import (
    DepthCaptionRequest,
    DepthCaptionJobResponse,
    DepthCaptionJobStatus,
    StylePreset,
    DepthMode,
)
from depth_captions.pipeline import create_depth_captions_job
from clip_generation.repository import ClipRepository
from clip_generation.service import clip_source
from core.database import AsyncSessionLocal
from clip_generation.model import GeneratedClip

log = get_logger(__name__)

depth_captions = APIRouter(prefix="/depth-captions", tags=["depth-captions"])


class DepthCaptionsRenderRequest(BaseModel):
    project_id: str
    clip_id: str
    style: StylePreset = StylePreset.GIANT_EDITORIAL
    depth_mode: DepthMode = DepthMode.AUTO
    language: str = "en"


class DepthCaptionsJobStatusResponse(BaseModel):
    job_id: str
    status: DepthCaptionJobStatus
    progress: int
    stage: str
    preview_url: Optional[str] = None
    output_url: Optional[str] = None
    error: Optional[str] = None


# In-memory job storage (in production, use Redis or database)
_job_store: dict[str, DepthCaptionJobResponse] = {}


@depth_captions.post("/render", response_model=DepthCaptionJobResponse)
async def start_depth_captions_render(
    request: DepthCaptionsRenderRequest,
    user: CurrentUserDep,
    background_tasks: BackgroundTasks,
):
    """Start a depth captions rendering job"""
    
    # Verify clip exists and user owns it
    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        clip = await repo.get_clip(request.clip_id, user["user_id"])
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        if clip.project_id != request.project_id:
            raise HTTPException(status_code=403, detail="Clip does not belong to project")
        
        if not clip.s3_key and not clip.local_path:
            raise HTTPException(status_code=400, detail="Clip video file not available")
        
        # Parse transcript
        import json
        transcript_segments = []
        if clip.transcript:
            try:
                transcript_data = json.loads(clip.transcript)
                for seg in transcript_data:
                    transcript_segments.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": seg.get("text", ""),
                        "speaker": seg.get("speaker"),
                        "words": seg.get("words", []),
                    })
            except json.JSONDecodeError:
                pass
    
    # Create job
    job_id = str(uuid4())
    job_response = DepthCaptionJobResponse(
        job_id=job_id,
        status=DepthCaptionJobStatus.QUEUED,
        progress=0,
        stage="queued",
    )
    _job_store[job_id] = job_response
    
    # Convert transcript segments
    from depth_captions.schema import TranscriptSegment
    segments = [TranscriptSegment(**s) for s in transcript_segments]
    
    # Create depth caption request
    dc_request = DepthCaptionRequest(
        project_id=request.project_id,
        clip_id=request.clip_id,
        style=request.style,
        depth_mode=request.depth_mode,
        language=request.language,
    )
    
    # Run in background
    async def run_job():
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
    
    background_tasks.add_task(run_job)
    
    return job_response


@depth_captions.get("/jobs/{job_id}", response_model=DepthCaptionsJobStatusResponse)
async def get_job_status(job_id: str, user: CurrentUserDep):
    """Get the status of a depth captions job"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = _job_store[job_id]
    return DepthCaptionsJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        preview_url=job.preview_url,
        output_url=job.output_url,
        error=job.error,
    )


@depth_captions.get("/jobs", response_model=list[DepthCaptionsJobStatusResponse])
async def list_jobs(user: CurrentUserDep):
    """List all depth captions jobs for the user"""
    return [
        DepthCaptionsJobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            stage=job.stage,
            preview_url=job.preview_url,
            output_url=job.output_url,
            error=job.error,
        )
        for job in _job_store.values()
    ]


@depth_captions.delete("/jobs/{job_id}")
async def cancel_job(job_id: str, user: CurrentUserDep):
    """Cancel a depth captions job"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = _job_store[job_id]
    if job.status in [DepthCaptionJobStatus.COMPLETED, DepthCaptionJobStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Job already completed")
    
    # In production, actually cancel the background task
    _job_store[job_id] = DepthCaptionJobResponse(
        job_id=job_id,
        status=DepthCaptionJobStatus.FAILED,
        progress=job.progress,
        stage="cancelled",
        error="Job cancelled by user",
    )
    
    return {"message": "Job cancelled"}


@depth_captions.get("/styles")
async def list_depth_caption_styles(user: CurrentUserDep):
    """List available depth caption style presets"""
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


@depth_captions.get("/depth-modes")
async def list_depth_modes(user: CurrentUserDep):
    """List available depth modes"""
    return {
        "modes": [
            {"id": mode.value, "name": mode.value.replace("_", " ").title()}
            for mode in DepthMode
        ]
    }