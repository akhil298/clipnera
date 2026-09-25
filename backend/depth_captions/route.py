from fastapi import APIRouter, BackgroundTasks, Depends

from auth.dependencies import CurrentUserDep
from subscription.dependencies import require_feature
from depth_captions.schema import (
    DepthCaptionJobResponse,
    DepthCaptionsJobStatusResponse,
    DepthCaptionsRenderRequest,
)
from depth_captions.service import DepthCaptionsService

depth_captions = APIRouter(prefix="/depth-captions", tags=["depth-captions"])
_service = DepthCaptionsService()


@depth_captions.post(
    "/render",
    response_model=DepthCaptionJobResponse,
    dependencies=[Depends(require_feature("depth_captions"))],
)
async def start_depth_captions_render(
    request: DepthCaptionsRenderRequest,
    user: CurrentUserDep,
    background_tasks: BackgroundTasks,
):
    """Start a depth captions rendering job"""
    return await _service.start_render(request, user["user_id"], background_tasks.add_task)


@depth_captions.get("/jobs/{job_id}", response_model=DepthCaptionsJobStatusResponse)
async def get_job_status(job_id: str, user: CurrentUserDep):
    """Get the status of a depth captions job"""
    return _service.get_job_status(job_id)


@depth_captions.get("/jobs", response_model=list[DepthCaptionsJobStatusResponse])
async def list_jobs(user: CurrentUserDep):
    """List all depth captions jobs for the user"""
    return _service.list_jobs()


@depth_captions.delete("/jobs/{job_id}")
async def cancel_job(job_id: str, user: CurrentUserDep):
    """Cancel a depth captions job"""
    return _service.cancel_job(job_id)


@depth_captions.get("/styles")
async def list_depth_caption_styles(user: CurrentUserDep):
    """List available depth caption style presets"""
    return _service.list_styles()


@depth_captions.get("/depth-modes")
async def list_depth_modes(user: CurrentUserDep):
    """List available depth modes"""
    return _service.list_depth_modes()
