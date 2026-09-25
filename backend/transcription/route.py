from fastapi import APIRouter, Depends, HTTPException

from transcription.schema import (
    BatchTranscriptionRequest,
    BatchTranscriptionResult,
    TranscriptionRequest,
    TranscriptionResult,
)
from transcription.service import WhisperXTranscriptionService
from core.exceptions import CustomException
from subscription.dependencies import require_feature
from core.logging_config import get_logger

log = get_logger(__name__)

transcription = APIRouter(prefix="/transcription", tags=["transcription"])
_service = WhisperXTranscriptionService()


@transcription.post("/transcribe", response_model=TranscriptionResult)
async def transcribe_audio(request: TranscriptionRequest):
    try:
        return await _service.transcribe_request(request)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())
    except Exception as exc:
        log.error(f"Transcription endpoint error: {exc}")
        raise HTTPException(status_code=500, detail={"error": "TRANSCRIPTION_FAILED", "message": str(exc)})


@transcription.post(
    "/batch",
    response_model=BatchTranscriptionResult,
    dependencies=[Depends(require_feature("batch_processing"))],
)
async def batch_transcribe_audio(request: BatchTranscriptionRequest):
    try:
        return await _service.batch_transcribe(request)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())
    except Exception as exc:
        log.error(f"Batch transcription endpoint error: {exc}")
        raise HTTPException(status_code=500, detail={"error": "BATCH_TRANSCRIPTION_FAILED", "message": str(exc)})
