from fastapi import APIRouter, Depends, HTTPException

from audio.extraction.schema import (
    BatchExtractionRequest,
    BatchExtractionResult,
    ExtractionRequest,
    ExtractionResult,
)
from audio.extraction.service import AudioExtractionService
from core.exceptions import CustomException
from subscription.dependencies import require_feature
from core.logging_config import get_logger

log = get_logger(__name__)

extraction = APIRouter(prefix="/audio/extraction", tags=["audio-extraction"])
_service = AudioExtractionService()


@extraction.post("/extract", response_model=ExtractionResult)
async def extract_audio(request: ExtractionRequest):
    try:
        return await _service.extract(request)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())
    except Exception as exc:
        log.error(f"Extraction endpoint error: {exc}")
        raise HTTPException(status_code=500, detail={"error": "EXTRACTION_FAILED", "message": str(exc)})


@extraction.post(
    "/batch",
    response_model=BatchExtractionResult,
    dependencies=[Depends(require_feature("batch_processing"))],
)
async def batch_extract_audio(request: BatchExtractionRequest):
    try:
        return await _service.batch_extract(request)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())
    except Exception as exc:
        log.error(f"Batch extraction endpoint error: {exc}")
        raise HTTPException(status_code=500, detail={"error": "BATCH_EXTRACTION_FAILED", "message": str(exc)})
