from fastapi import APIRouter, Depends

from auth.dependencies import CurrentUserDep
from audio.enhancement.schema import AudioEnhanceRequest, AudioEnhanceResponse, AudioPreviewRequest
from audio.enhancement.service import AudioService
from subscription.dependencies import check_limit

audio = APIRouter(prefix="/audio", tags=["audio"])
_service = AudioService()


@audio.post(
    "/process", response_model=AudioEnhanceResponse,
    dependencies=[Depends(check_limit("audio_enhancements"))],
)
async def process_audio(request: AudioEnhanceRequest, user: CurrentUserDep):
    return await _service.process_audio_from_url(request)


@audio.post("/preview", response_model=AudioEnhanceResponse)
async def preview_audio(request: AudioPreviewRequest, user: CurrentUserDep):
    return await _service.generate_preview(request)


@audio.get("/presets", tags=["audio"])
async def get_presets(user: CurrentUserDep = None):
    return _service.list_presets()
