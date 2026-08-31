from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Callable

from audio.extraction.schema import (
    AudioChannel,
    AudioCodec,
    BatchExtractionRequest,
    BatchExtractionResult,
    ExtractionProgress,
    ExtractionRequest,
    ExtractionResult,
    OutputFormat,
)
from audio.extraction.ffmpeg_runner import FFmpegRunner
from audio.extraction.manifest import ManifestGenerator
from core.exceptions import CustomException
from core.logging_config import get_logger

log = get_logger(__name__)

CODEC_MAP = {
    OutputFormat.WAV: AudioCodec.PCM.value,
    OutputFormat.MP3: AudioCodec.MP3.value,
    OutputFormat.AAC: AudioCodec.AAC.value,
    OutputFormat.FLAC: AudioCodec.FLAC.value,
    OutputFormat.OPUS: AudioCodec.OPUS.value,
}


class AudioExtractionService:
    def __init__(self) -> None:
        self._runner = FFmpegRunner()

    def _resolve_output_path(self, request: ExtractionRequest) -> str:
        if request.output_path:
            return request.output_path
        input_path = Path(request.input_path)
        ext = request.output_format.value
        return str(input_path.with_suffix(f".{ext}"))

    def _check_disk_space(self, output_path: str, estimated_bytes: int) -> None:
        try:
            target_dir = Path(output_path).parent
            usage = shutil.disk_usage(target_dir)
            free = usage.free
            if free < estimated_bytes:
                raise CustomException(
                    message=(
                        f"Insufficient disk space. Required: {estimated_bytes / (1024**3):.2f} GB, "
                        f"Available: {free / (1024**3):.2f} GB"
                    ),
                    code="INSUFFICIENT_DISK_SPACE",
                    status_code=507,
                )
        except OSError as exc:
            log.warning(f"Disk space check failed: {exc}")

    async def extract(self, request: ExtractionRequest, progress_callback: Callable[[ExtractionProgress], None] | None = None) -> ExtractionResult:
        start = time.time()
        input_path = request.input_path
        if not os.path.exists(input_path):
            raise CustomException(message=f"Input file not found: {input_path}", code="FILE_NOT_FOUND", status_code=404)

        output_path = self._resolve_output_path(request)
        codec = request.codec.value if request.codec else CODEC_MAP.get(request.output_format, AudioCodec.PCM.value)
        channels = request.channels.value

        source_duration = await self._runner.probe_duration(input_path)
        estimated_bytes = int(source_duration * request.sample_rate * 2 * (1 if channels == "mono" else 2) * 1.2)
        self._check_disk_space(output_path, estimated_bytes)

        warnings: list[str] = []

        def _on_progress(prog) -> None:
            percent = prog.percent
            if source_duration > 0 and prog.out_time_us > 0:
                current_time = prog.out_time_us / 1_000_000
                percent = min(100.0, (current_time / source_duration) * 100)
            if progress_callback:
                progress_callback(ExtractionProgress(
                    percent=round(percent, 1),
                    frame=prog.frame,
                    fps=prog.fps,
                    bitrate=prog.bitrate,
                    total_size=prog.total_size,
                    out_time_us=prog.out_time_us,
                    speed=prog.speed,
                    status=prog.status,
                ))

        try:
            returncode, stdout, stderr = await self._runner.run(
                input_path=input_path,
                output_path=output_path,
                codec=codec,
                sample_rate=request.sample_rate,
                channels=channels,
                overwrite=request.overwrite,
                progress_callback=_on_progress,
            )
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(message=f"Extraction failed: {exc}", code="EXTRACTION_FAILED", status_code=500) from exc

        if returncode != 0:
            error_msg = stderr or stdout or f"FFmpeg exited with code {returncode}"
            raise CustomException(message=f"FFmpeg error: {error_msg}", code="FFMPEG_ERROR", status_code=500)

        if not os.path.exists(output_path):
            raise CustomException(message="Output file was not created", code="OUTPUT_MISSING", status_code=500)

        output_duration = await self._runner.get_output_duration(output_path)
        sync_warning = ManifestGenerator.validate_sync(source_duration, output_duration)
        if sync_warning:
            warnings.append(sync_warning)

        if source_duration == 0:
            warnings.append("Source duration could not be determined; sync validation skipped.")

        file_size = os.path.getsize(output_path)
        processing_time = time.time() - start

        manifest = ManifestGenerator.generate(
            input_path=input_path,
            output_path=output_path,
            source_duration=source_duration,
            output_duration=output_duration,
            sample_rate=request.sample_rate,
            channels=2 if channels == "stereo" else 1,
            codec=codec,
            format=request.output_format.value,
            file_size_bytes=file_size,
            warnings=warnings,
            processing_time_seconds=processing_time,
        )
        ManifestGenerator.save(manifest, output_path)

        log.info(f"Extraction completed: {input_path} -> {output_path} ({processing_time:.2f}s)")
        return ExtractionResult(
            input_path=input_path,
            output_path=output_path,
            format=request.output_format.value,
            codec=codec,
            sample_rate=request.sample_rate,
            channels=2 if channels == "stereo" else 1,
            duration_seconds=round(output_duration, 3),
            file_size_bytes=file_size,
            status="completed",
            warnings=warnings,
            processing_time_seconds=round(processing_time, 3),
        )

    async def batch_extract(self, request: BatchExtractionRequest) -> BatchExtractionResult:
        start = time.time()
        semaphore = asyncio.Semaphore(request.max_workers)
        results: list[ExtractionResult] = []

        async def _process_one(input_path: str) -> ExtractionResult:
            async with semaphore:
                try:
                    return await self.extract(ExtractionRequest(
                        input_path=input_path,
                        output_dir=request.output_dir,
                        output_format=request.output_format,
                        sample_rate=request.sample_rate,
                        channels=request.channels,
                        overwrite=request.overwrite,
                    ))
                except CustomException as exc:
                    log.error(f"Batch extraction failed for {input_path}: {exc.message}")
                    base = Path(input_path)
                    return ExtractionResult(
                        input_path=input_path,
                        output_path=str(Path(request.output_dir) / f"{base.stem}.{request.output_format.value}"),
                        format=request.output_format.value,
                        codec="unknown",
                        sample_rate=request.sample_rate,
                        channels=1,
                        duration_seconds=0.0,
                        file_size_bytes=0,
                        status="failed",
                        error=exc.message,
                    )
                except Exception as exc:
                    log.error(f"Batch extraction unexpected error for {input_path}: {exc}")
                    base = Path(input_path)
                    return ExtractionResult(
                        input_path=input_path,
                        output_path=str(Path(request.output_dir) / f"{base.stem}.{request.output_format.value}"),
                        format=request.output_format.value,
                        codec="unknown",
                        sample_rate=request.sample_rate,
                        channels=1,
                        duration_seconds=0.0,
                        file_size_bytes=0,
                        status="failed",
                        error=str(exc),
                    )

        tasks = [_process_one(p) for p in request.input_paths]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        completed = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        processing_time = time.time() - start

        log.info(f"Batch extraction done: {completed}/{len(results)} completed in {processing_time:.2f}s")
        return BatchExtractionResult(
            total=len(results),
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=results,
            processing_time_seconds=round(processing_time, 3),
        )
