from fastapi import APIRouter, HTTPException

from auth.dependencies import CurrentUserDep
from audio.enhancement.schema import AudioEnhanceRequest, AudioEnhanceResponse, AudioPreviewRequest
from audio.enhancement.service import AudioService
from core.logging_config import get_logger

log = get_logger(__name__)

audio = APIRouter(prefix="/audio", tags=["audio"])
_service = AudioService()


@audio.post("/process", response_model=AudioEnhanceResponse)
async def process_audio(request: AudioEnhanceRequest, user: CurrentUserDep):
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(request.audio_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch audio from provided URL")
        audio_bytes = resp.content
    return await _service.process_audio(request, audio_bytes)


@audio.post("/preview", response_model=AudioEnhanceResponse)
async def preview_audio(request: AudioPreviewRequest, user: CurrentUserDep):
    return await _service.generate_preview(request)


@audio.get("/presets", tags=["audio"])
async def get_presets(user: CurrentUserDep = None):
    from audio.enhancement.service import ZONE_PRESETS
    return {
        "zones": [
            {"key": k, "label": v["label"], "strength_range": "0-30" if k == "mild" else "31-70" if k == "balanced" else "71-100"}
            for k, v in ZONE_PRESETS.items()
        ]
    }
