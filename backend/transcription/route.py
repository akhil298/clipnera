from fastapi import APIRouter, HTTPException
from typing import Any, Callable

from transcription.schema import (
    BatchTranscriptionRequest,
    BatchTranscriptionResult,
    TranscriptionRequest,
    TranscriptionResult,
)
from transcription.service import WhisperXTranscriptionService
from core.exceptions import CustomException
from core.logging_config import get_logger

log = get_logger(__name__)

transcription = APIRouter(prefix="/transcription", tags=["transcription"])
_service = WhisperXTranscriptionService()


@transcription.post("/transcribe", response_model=TranscriptionResult)
async def transcribe_audio(request: TranscriptionRequest):
    try:
        def _progress(percent: float, message: str) -> None:
            log.info(f"Transcription progress: {percent:.1f}% - {message}")

        result = await _service.transcribe(request, progress_callback=_progress)
        return TranscriptionResult(**result)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())
    except Exception as exc:
        log.error(f"Transcription endpoint error: {exc}")
        raise HTTPException(status_code=500, detail={"error": "TRANSCRIPTION_FAILED", "message": str(exc)})


@transcription.post("/batch", response_model=BatchTranscriptionResult)
async def batch_transcribe_audio(request: BatchTranscriptionRequest):
    try:
        tasks = []
        for input_path in request.input_paths:
            single = TranscriptionRequest(
                input_path=input_path,
                model_size=request.model_size,
                language=request.language,
                chunk_duration=request.chunk_duration,
                chunk_overlap=request.chunk_overlap,
                word_timestamps=request.word_timestamps,
                diarization=request.diarization,
                output_format=request.output_format,
                output_dir=request.output_dir,
                device=request.device,
            )
            tasks.append(_service.transcribe(single))

        import asyncio
        semaphore = asyncio.Semaphore(request.max_workers)
        async def _run(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[_run(t) for t in tasks], return_exceptions=False)
        completed = sum(1 for r in results if not isinstance(r, Exception))
        failed = sum(1 for r in results if isinstance(r, Exception))

        final_results = []
        for r in results:
            if isinstance(r, Exception):
                log.error(f"Batch transcription failed: {r}")
                continue
            final_results.append(TranscriptionResult(**r))

        import time as _time
        return BatchTranscriptionResult(
            total=len(request.input_paths),
            completed=completed,
            failed=failed,
            results=final_results,
            processing_time_seconds=0.0,
        )
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())
    except Exception as exc:
        log.error(f"Batch transcription endpoint error: {exc}")
        raise HTTPException(status_code=500, detail={"error": "BATCH_TRANSCRIPTION_FAILED", "message": str(exc)})
