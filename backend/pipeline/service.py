from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from core.logging_config import get_logger

from clip.youtube_service import YouTubeService
from audio.extraction.service import AudioExtractionService
from audio.enhancement.service import AudioService
from audio.enhancement.schema import AudioEnhanceRequest
from clip.repository import ClipRepository
from core.database import AsyncSessionLocal

from pipeline.model import PipelineStepType, StepStatus

log = get_logger(__name__)


ProgressCallback = Callable[[str, int, Optional[str]], None]


class PipelineOrchestrator:
    def __init__(
        self,
        project_id: str,
        user_id: str,
        url: str,
        selected_steps: list[PipelineStepType],
        audio_config: Optional[dict] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        self.project_id = project_id
        self.user_id = user_id
        self.url = url
        self.selected_steps = selected_steps
        self.audio_config = audio_config or {}
        self.progress_callback = progress_callback
        self._youtube = YouTubeService()
        self._audio_extractor = AudioExtractionService()
        self._audio_service = AudioService()
        self._cancel = False
        self._local_path: str | None = None

    def cancel(self) -> None:
        self._cancel = True

    async def run(self) -> dict:
        results: dict[str, Any] = {}
        step_order = [
            PipelineStepType.DOWNLOAD,
            PipelineStepType.AUDIO_EXTRACTION,
            PipelineStepType.AI_NOISE_CANCELLATION,
            PipelineStepType.TRANSCRIPTION,
            PipelineStepType.CLIP_GENERATION,
            PipelineStepType.CAPTION_STYLING,
            PipelineStepType.AUTO_REFAME,
            PipelineStepType.EXPORT,
        ]

        for step in step_order:
            if self._cancel:
                break
            if step not in self.selected_steps:
                continue

            try:
                await self._mark_step_running(step)
                result = await self._execute_step(step, results)
                results[step.value] = result
                await self._mark_step_completed(step, result)
            except Exception as exc:
                log.error(f"Pipeline step failed: step={step.value} project={self.project_id} error={exc}")
                await self._mark_step_failed(step, str(exc))
                raise

        return results

    async def _execute_step(self, step: PipelineStepType, context: dict) -> Any:
        if step == PipelineStepType.DOWNLOAD:
            return await self._step_download()
        if step == PipelineStepType.AUDIO_EXTRACTION:
            return await self._step_audio_extraction(context)
        if step == PipelineStepType.AI_NOISE_CANCELLATION:
            return await self._step_ai_noise_cancellation(context)
        if step == PipelineStepType.TRANSCRIPTION:
            return await self._step_transcription(context)
        if step == PipelineStepType.CLIP_GENERATION:
            return await self._step_clip_generation(context)
        if step == PipelineStepType.CAPTION_STYLING:
            return await self._step_caption_styling(context)
        if step == PipelineStepType.AUTO_REFAME:
            return await self._step_auto_reframe(context)
        if step == PipelineStepType.EXPORT:
            return await self._step_export(context)
        raise ValueError(f"Unknown pipeline step: {step.value}")

    async def _step_download(self) -> dict:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project = await repo.get_project(self.project_id, self.user_id)
            if project and project.local_path and Path(project.local_path).exists():
                self._notify("Video already downloaded, skipping...", 100)
                self._local_path = project.local_path
                return {"local_path": project.local_path, "skipped": True}

        self._notify("Downloading video...", 0)
        result = await self._youtube.download_and_store(self.url, self.user_id, self.project_id)
        self._local_path = result.get("local_path")
        self._notify("Download complete", 100)
        return result

    async def _step_audio_extraction(self, context: dict) -> dict:
        download_result = context.get(PipelineStepType.DOWNLOAD.value, {})
        video_path = download_result.get("local_path") or self._local_path

        if not video_path or not Path(video_path).exists():
            async with AsyncSessionLocal() as session:
                repo = ClipRepository(session)
                project = await repo.get_project(self.project_id, self.user_id)
                if project and project.local_path and Path(project.local_path).exists():
                    video_path = project.local_path
                    self._local_path = video_path

        if not video_path or not Path(video_path).exists():
            raise ValueError(
                "Missing downloaded video path for audio extraction. "
                "Run the 'download' step first or ensure the local file still exists."
            )

        self._notify("Extracting audio track...", 10)
        from audio.extraction.schema import ExtractionRequest, OutputFormat, AudioChannel
        request = ExtractionRequest(
            input_path=video_path,
            output_format=OutputFormat.WAV,
            sample_rate=16000,
            channels=AudioChannel.MONO,
            overwrite=True,
        )
        result = await self._audio_extractor.extract(request)
        self._notify("Audio extracted", 100)
        return {"extraction_result": result.model_dump()}

    async def _step_ai_noise_cancellation(self, context: dict) -> dict:
        extraction = context.get(PipelineStepType.AUDIO_EXTRACTION.value, {})
        audio_path = extraction.get("extraction_result", {}).get("output_path")
        if not audio_path:
            raise ValueError("Missing extracted audio path for noise cancellation")

        self._notify("Running AI noise cancellation...", 20)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        request = AudioEnhanceRequest(audio_url=f"file://{audio_path}", config=self.audio_config)
        result = await self._audio_service.process_audio(request, audio_bytes)

        before_path = audio_path
        after_path = f"/tmp/{self.project_id}_enhanced.wav"

        if result.success and result.processed_url:
            processed_bytes = await self._fetch_processed_bytes(result.processed_url)
            with open(after_path, "wb") as f:
                f.write(processed_bytes)

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project = await repo.get_project(self.project_id, self.user_id)
            if project:
                project.audio_original_url = before_path
                project.audio_processed_url = after_path if result.success else None
                project.audio_reverted = False
                await session.commit()

        self._notify("AI noise cancellation complete", 100)
        return {
            "before_audio_path": before_path,
            "after_audio_path": after_path,
            "enhancement_result": result.model_dump(),
        }

    async def _step_transcription(self, context: dict) -> dict:
        self._notify("Transcribing audio...", 10)
        return {"status": "skipped", "message": "Transcription placeholder"}

    async def _step_clip_generation(self, context: dict) -> dict:
        self._notify("Generating viral clips...", 10)
        return {"status": "skipped", "message": "Clip generation placeholder"}

    async def _step_caption_styling(self, context: dict) -> dict:
        self._notify("Applying captions...", 10)
        return {"status": "skipped", "message": "Caption styling placeholder"}

    async def _step_auto_reframe(self, context: dict) -> dict:
        self._notify("Auto-reframing video...", 10)
        return {"status": "skipped", "message": "Auto-reframe placeholder"}

    async def _step_export(self, context: dict) -> dict:
        self._notify("Exporting final video...", 10)
        return {"status": "skipped", "message": "Export placeholder"}

    async def _mark_step_running(self, step: PipelineStepType) -> None:
        self._notify(f"Starting {step.value}...", 0)

    async def _mark_step_completed(self, step: PipelineStepType, result: Any) -> None:
        self._notify(f"Completed {step.value}", 100)

    async def _mark_step_failed(self, step: PipelineStepType, error: str) -> None:
        self._notify(f"Failed: {step.value} - {error}", 0)

    def _notify(self, message: str, percent: int) -> None:
        if self.progress_callback:
            try:
                result = self.progress_callback(message, percent, None)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                log.debug(f"Progress notify failed: {e}")

    async def _fetch_processed_bytes(self, url: str) -> bytes:
        if url.startswith("processed://") or url.startswith("preview://"):
            return b""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
