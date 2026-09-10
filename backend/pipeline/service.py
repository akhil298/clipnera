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
from transcription.service import WhisperXTranscriptionService
from transcription.schema import TranscriptionRequest
from clip.repository import ClipRepository
from clip_generation.service import ClipService
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
        watermark_enabled: bool = True,
    ) -> None:
        log.info(
            "Pipeline orchestrator initialized",
            extra={
                "project_id": project_id,
                "user_id": user_id,
                "url": url,
                "selected_steps": [s.value for s in selected_steps],
                "watermark_enabled": watermark_enabled,
            },
        )
        self.project_id = project_id
        self.user_id = user_id
        self.url = url
        self.selected_steps = selected_steps
        self.audio_config = audio_config or {}
        self.progress_callback = progress_callback
        self.watermark_enabled = watermark_enabled
        self._youtube = YouTubeService()
        self._audio_extractor = AudioExtractionService()
        self._audio_service = AudioService()
        self._transcription_service = WhisperXTranscriptionService()
        self._clip_service = ClipService()
        self._cancel = False
        self._local_path: str | None = None

    def cancel(self) -> None:
        self._cancel = True
        log.warning(
            "Pipeline cancel requested",
            extra={"project_id": self.project_id, "user_id": self.user_id},
        )

    async def run(self) -> dict:
        results: dict[str, Any] = {}
        step_order = [
            PipelineStepType.DOWNLOAD,
            PipelineStepType.AUDIO_EXTRACTION,
            PipelineStepType.AI_NOISE_CANCELLATION,
            PipelineStepType.TRANSCRIPTION,
            PipelineStepType.TOPIC_RESEARCH,
            PipelineStepType.VISUAL_ANALYSIS,
            PipelineStepType.CONTENT_CLASSIFICATION,
            PipelineStepType.HIGHLIGHT_DETECTION,
            PipelineStepType.SCORING,
            PipelineStepType.METADATA_GENERATION,
            PipelineStepType.CLIP_GENERATION,
            PipelineStepType.SUBTITLE_STYLING,
            PipelineStepType.BURN_IN_EXPORT,
        ]

        log.info(
            "Pipeline started",
            extra={
                "project_id": self.project_id,
                "user_id": self.user_id,
                "url": self.url,
                "selected_steps": [s.value for s in self.selected_steps],
                "total_steps": len(step_order),
            },
        )

        try:
            for step in step_order:
                if self._cancel:
                    log.warning(
                        "Pipeline cancelled",
                        extra={"project_id": self.project_id, "user_id": self.user_id, "step": step.value},
                    )
                    break
                if step not in self.selected_steps:
                    log.debug(
                        "Step skipped (not selected)",
                        extra={"project_id": self.project_id, "step": step.value},
                    )
                    continue

                try:
                    await self._mark_step_running(step)
                    result = await self._execute_step(step, results)
                    results[step.value] = result
                    await self._mark_step_completed(step, result)
                except Exception as exc:
                    log.error(
                        "Pipeline step failed",
                        extra={
                            "project_id": self.project_id,
                            "user_id": self.user_id,
                            "step": step.value,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    )
                    await self._mark_step_failed(step, str(exc))
                    raise

            log.info(
                "Pipeline finished",
                extra={
                    "project_id": self.project_id,
                    "user_id": self.user_id,
                    "completed_steps": list(results.keys()),
                    "canceled": self._cancel,
                },
            )
            await self._mark_pipeline_completed()
        except Exception as exc:
            await self._mark_pipeline_failed(str(exc))
            raise
        return results

    async def _execute_step(self, step: PipelineStepType, context: dict) -> Any:
        log.info(
            "Executing pipeline step",
            extra={"project_id": self.project_id, "step": step.value},
        )
        if step == PipelineStepType.DOWNLOAD:
            return await self._step_download()
        if step == PipelineStepType.AUDIO_EXTRACTION:
            return await self._step_audio_extraction(context)
        if step == PipelineStepType.AI_NOISE_CANCELLATION:
            return await self._step_ai_noise_cancellation(context)
        if step == PipelineStepType.TRANSCRIPTION:
            return await self._step_transcription(context)
        if step == PipelineStepType.TOPIC_RESEARCH:
            return await self._step_topic_research(context)
        if step == PipelineStepType.VISUAL_ANALYSIS:
            return await self._step_visual_analysis(context)
        if step == PipelineStepType.CONTENT_CLASSIFICATION:
            return await self._step_content_classification(context)
        if step == PipelineStepType.HIGHLIGHT_DETECTION:
            return await self._step_highlight_detection(context)
        if step == PipelineStepType.SCORING:
            return await self._step_scoring(context)
        if step == PipelineStepType.METADATA_GENERATION:
            return await self._step_metadata_generation(context)
        if step == PipelineStepType.CLIP_GENERATION:
            return await self._step_clip_generation(context)
        if step == PipelineStepType.SUBTITLE_STYLING:
            return await self._step_subtitle_styling(context)
        if step == PipelineStepType.BURN_IN_EXPORT:
            return await self._step_burn_in_export(context)
        raise ValueError(f"Unknown pipeline step: {step.value}")

    async def _step_download(self) -> dict:
        log.info("Checking for existing downloaded video", extra={"project_id": self.project_id, "url": self.url})
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project = await repo.get_project(self.project_id, self.user_id)
            if project and project.local_path and Path(project.local_path).exists():
                log.info(
                    "Video already downloaded, skipping",
                    extra={"project_id": self.project_id, "local_path": project.local_path},
                )
                self._notify("Video already downloaded, skipping...", 100)
                self._local_path = project.local_path
                return {"local_path": project.local_path, "skipped": True}

        log.info("Starting video download", extra={"project_id": self.project_id, "url": self.url})
        self._notify("Downloading video...", 0)
        result = await self._youtube.download_and_store(self.url, self.user_id, self.project_id)
        self._local_path = result.get("local_path")
        log.info(
            "Download complete",
            extra={
                "project_id": self.project_id,
                "local_path": self._local_path,
                "file_size": result.get("file_size"),
                "duration_seconds": result.get("duration_seconds"),
            },
        )
        self._notify("Download complete", 100)
        return result

    async def _step_audio_extraction(self, context: dict) -> dict:
        download_result = context.get(PipelineStepType.DOWNLOAD.value, {})
        video_path = download_result.get("local_path") or self._local_path
        log.info("Resolving video path for audio extraction", extra={"project_id": self.project_id, "video_path": video_path})

        if not video_path or not Path(video_path).exists():
            async with AsyncSessionLocal() as session:
                repo = ClipRepository(session)
                project = await repo.get_project(self.project_id, self.user_id)
                if project and project.local_path and Path(project.local_path).exists():
                    video_path = project.local_path
                    self._local_path = video_path
                    log.info(
                        "Recovered video path from database",
                        extra={"project_id": self.project_id, "video_path": video_path},
                    )

        if not video_path or not Path(video_path).exists():
            raise ValueError(
                "Missing downloaded video path for audio extraction. "
                "Run the 'download' step first or ensure the local file still exists."
            )

        log.info("Starting audio extraction", extra={"project_id": self.project_id, "video_path": video_path})
        self._notify("Extracting audio track...", 10)
        from audio.extraction.schema import ExtractionRequest, OutputFormat, AudioChannel
        request = ExtractionRequest(
            input_path=video_path,
            output_format=OutputFormat.WAV,
            sample_rate=16000,
            channels=AudioChannel.MONO,
            overwrite=True,
        )
        log.info(
            "Audio extraction request",
            extra={
                "project_id": self.project_id,
                "input_path": request.input_path,
                "output_format": request.output_format.value,
                "sample_rate": request.sample_rate,
                "channels": request.channels.value,
            },
        )
        result = await self._audio_extractor.extract(request)
        log.info(
            "Audio extracted",
            extra={
                "project_id": self.project_id,
                "output_path": result.output_path,
                "duration_seconds": result.duration_seconds,
                "size_bytes": result.file_size_bytes,
            },
        )
        self._notify("Audio extracted", 100)
        return {"extraction_result": result.model_dump()}

    async def _step_ai_noise_cancellation(self, context: dict) -> dict:
        extraction = context.get(PipelineStepType.AUDIO_EXTRACTION.value, {})
        audio_path = extraction.get("extraction_result", {}).get("output_path")
        log.info("Resolving audio path for noise cancellation", extra={"project_id": self.project_id, "audio_path": audio_path})
        if not audio_path:
            raise ValueError("Missing extracted audio path for noise cancellation")

        self._notify("Running AI noise cancellation...", 20)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        log.info(
            "Audio bytes loaded for enhancement",
            extra={"project_id": self.project_id, "audio_path": audio_path, "size_bytes": len(audio_bytes)},
        )

        request = AudioEnhanceRequest(audio_url=f"file://{audio_path}", config=self.audio_config)
        log.info(
            "Starting AI noise cancellation",
            extra={"project_id": self.project_id, "audio_path": audio_path, "config": self.audio_config},
        )
        result = await self._audio_service.process_audio(request, audio_bytes)

        before_path = audio_path
        after_path = f"/tmp/{self.project_id}_enhanced.wav"
        log.info(
            "Noise cancellation result",
            extra={
                "project_id": self.project_id,
                "success": result.success,
                "processed_url": result.processed_url,
                "before_path": before_path,
                "after_path": after_path,
            },
        )

        if result.success and result.processed_url:
            processed_bytes = await self._fetch_processed_bytes(result.processed_url)
            with open(after_path, "wb") as f:
                f.write(processed_bytes)
            log.info(
                "Enhanced audio saved",
                extra={"project_id": self.project_id, "after_path": after_path, "size_bytes": len(processed_bytes)},
            )

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
        download_result = context.get(PipelineStepType.DOWNLOAD.value, {})
        video_path = download_result.get("local_path") or self._local_path
        log.info("Resolving video path for transcription", extra={"project_id": self.project_id, "video_path": video_path})

        if not video_path or not Path(video_path).exists():
            async with AsyncSessionLocal() as session:
                repo = ClipRepository(session)
                project = await repo.get_project(self.project_id, self.user_id)
                if project and project.local_path and Path(project.local_path).exists():
                    video_path = project.local_path
                    self._local_path = video_path
                    log.info(
                        "Recovered video path from database",
                        extra={"project_id": self.project_id, "video_path": video_path},
                    )

        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for transcription")

        log.info("Starting transcription", extra={"project_id": self.project_id, "video_path": video_path})
        self._notify("Transcribing audio...", 10)

        request = TranscriptionRequest(
            input_path=video_path,
            model_size="small",
            language=None,
            chunk_duration=1200,
            chunk_overlap=10,
            word_timestamps=True,
            diarization=True,
            output_format="all",
            device="cpu",
        )
        log.info(
            "Transcription request",
            extra={
                "project_id": self.project_id,
                "input_path": request.input_path,
                "model_size": request.model_size,
                "chunk_duration": request.chunk_duration,
                "device": request.device,
            },
        )

        def _progress(percent: float, message: str):
            self._notify(f"Transcription: {message}", int(percent))

        result = await self._transcription_service.transcribe(request, progress_callback=_progress)
        segments = getattr(result, "segments", [])
        log.info(
            "Transcription complete",
            extra={
                "project_id": self.project_id,
                "segment_count": len(segments),
                "duration_seconds": getattr(result, "duration_seconds", None),
            },
        )
        self._notify("Transcription complete", 100)
        return {"transcription_result": result}

    async def _step_topic_research(self, context: dict) -> dict:
        self._notify("Researching topic...", 20)
        transcription = context.get(PipelineStepType.TRANSCRIPTION.value, {})
        transcript_result = transcription.get("transcription_result", {})
        segments = transcript_result.get("segments", [])
        log.info(
            "Starting topic research",
            extra={"project_id": self.project_id, "segment_count": len(segments)},
        )

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService()

        video_path = self._local_path
        if not video_path or not Path(video_path).exists():
            async with AsyncSessionLocal() as session:
                repo = ClipRepository(session)
                project = await repo.get_project(self.project_id, self.user_id)
                if project and project.local_path and Path(project.local_path).exists():
                    video_path = project.local_path
                    log.info(
                        "Recovered video path from database for topic research",
                        extra={"project_id": self.project_id, "video_path": video_path},
                    )

        analysis = await service.analyze_project(
            project_id=self.project_id,
            video_path=video_path,
            transcript_segments=segments,
            progress_callback=lambda msg, pct, _: self._notify(msg, pct),
        )
        log.info(
            "Topic research complete",
            extra={"project_id": self.project_id, "analysis_keys": list(analysis.keys()) if isinstance(analysis, dict) else type(analysis).__name__},
        )
        self._notify("Topic research complete", 100)
        return {"topic_research": analysis.get("topic_research", {}), "analysis": analysis}

    async def _step_visual_analysis(self, context: dict) -> dict:
        self._notify("Analyzing video frames...", 20)
        log.info("Starting visual analysis", extra={"project_id": self.project_id})

        video_path = self._local_path
        if not video_path or not Path(video_path).exists():
            async with AsyncSessionLocal() as session:
                repo = ClipRepository(session)
                project = await repo.get_project(self.project_id, self.user_id)
                if project and project.local_path and Path(project.local_path).exists():
                    video_path = project.local_path
                    log.info(
                        "Recovered video path from database for visual analysis",
                        extra={"project_id": self.project_id, "video_path": video_path},
                    )

        from content_intelligence.analyzer import FrameAnalyzer
        from clients.ai.gemini import Gemini
        analyzer = FrameAnalyzer(Gemini())

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})
        category = analysis.get("classification", {}).get("category", "unknown")
        log.info(
            "Visual analysis request",
            extra={"project_id": self.project_id, "video_path": video_path, "category": category},
        )

        frame_result = await analyzer.analyze(video_path, category)
        log.info(
            "Visual analysis complete",
            extra={"project_id": self.project_id, "result_type": type(frame_result).__name__},
        )
        self._notify("Visual analysis complete", 100)
        return {"frame_analysis": frame_result}

    async def _step_content_classification(self, context: dict) -> dict:
        self._notify("Classifying content...", 50)
        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        transcription = context.get(PipelineStepType.TRANSCRIPTION.value, {})
        segments = transcription.get("transcription_result", {}).get("segments", [])
        log.info(
            "Starting content classification",
            extra={"project_id": self.project_id, "segment_count": len(segments)},
        )

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService()

        topic_research = topic.get("topic_research", {})
        classification = await service._classifier.classify(topic_research, segments)
        log.info(
            "Content classification complete",
            extra={"project_id": self.project_id, "classification": str(classification)},
        )
        self._notify("Content classification complete", 100)
        return {"classification": classification}

    async def _step_highlight_detection(self, context: dict) -> dict:
        self._notify("Detecting highlights...", 30)
        log.info("Starting highlight detection", extra={"project_id": self.project_id})

        video_path = self._local_path
        if not video_path or not Path(video_path).exists():
            async with AsyncSessionLocal() as session:
                repo = ClipRepository(session)
                project = await repo.get_project(self.project_id, self.user_id)
                if project and project.local_path and Path(project.local_path).exists():
                    video_path = project.local_path
                    log.info(
                        "Recovered video path from database for highlight detection",
                        extra={"project_id": self.project_id, "video_path": video_path},
                    )

        transcription = context.get(PipelineStepType.TRANSCRIPTION.value, {})
        segments = transcription.get("transcription_result", {}).get("segments", [])
        log.info(
            "Highlight detection inputs",
            extra={"project_id": self.project_id, "video_path": video_path, "segment_count": len(segments)},
        )

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService()

        highlights = await service.detect_highlights(
            project_id=self.project_id,
            video_path=video_path,
            transcript_segments=segments,
            analysis=analysis,
            progress_callback=lambda msg, pct, _: self._notify(msg, pct),
        )
        log.info(
            "Highlight detection complete",
            extra={"project_id": self.project_id, "highlight_count": len(highlights)},
        )
        self._notify(f"Found {len(highlights)} highlights", 100)
        return {"highlights": highlights}

    async def _step_scoring(self, context: dict) -> dict:
        self._notify("Scoring highlights...", 50)
        highlight_result = context.get(PipelineStepType.HIGHLIGHT_DETECTION.value, {})
        highlights = highlight_result.get("highlights", [])
        log.info(
            "Starting highlight scoring",
            extra={"project_id": self.project_id, "highlight_count": len(highlights)},
        )

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService()

        scored = await service.score_highlights(highlights, analysis)
        log.info(
            "Scoring complete",
            extra={"project_id": self.project_id, "scored_count": len(scored)},
        )
        self._notify("Scoring complete", 100)
        return {"scored_highlights": scored}

    async def _step_metadata_generation(self, context: dict) -> dict:
        self._notify("Generating metadata...", 50)
        score_result = context.get(PipelineStepType.SCORING.value, {})
        scored = score_result.get("scored_highlights", [])
        log.info(
            "Starting metadata generation",
            extra={"project_id": self.project_id, "scored_highlight_count": len(scored)},
        )

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService()

        final_clips = await service.generate_metadata_for_clips(scored)
        log.info(
            "Metadata generation complete",
            extra={"project_id": self.project_id, "final_clip_count": len(final_clips)},
        )
        self._notify("Metadata generation complete", 100)
        return {"final_clips": final_clips}

    async def _step_clip_generation(self, context: dict) -> dict:
        self._notify("Generating clips...", 30)
        meta_result = context.get(PipelineStepType.METADATA_GENERATION.value, {})
        final_clips = meta_result.get("final_clips", [])
        log.info(
            "Starting clip generation",
            extra={"project_id": self.project_id, "clip_count": len(final_clips)},
        )

        self._notify(f"Processing {len(final_clips)} clips...", 50)
        result = await self._clip_service.generate_clips_for_project(
            self.project_id, self.user_id,
            progress_callback=lambda msg, pct, _: self._notify(msg, pct),
        )
        log.info(
            "Clip generation complete",
            extra={"project_id": self.project_id, "result_type": type(result).__name__},
        )
        self._notify("Clip generation complete", 100)
        return result

    async def _step_subtitle_styling(self, context: dict) -> dict:
        self._notify("Preparing subtitle styles...", 100)
        log.info("Starting subtitle styling step", extra={"project_id": self.project_id})
        from subtitle_styling.service import SubtitleStylingService
        service = SubtitleStylingService()
        presets = await service.get_style_presets()
        log.info(
            "Subtitle styling step complete",
            extra={"project_id": self.project_id, "preset_count": len(presets)},
        )
        return {"presets": presets, "message": "User selects style before burn-in"}

    async def _step_burn_in_export(self, context: dict) -> dict:
        self._notify("Burning titles into clips...", 50)
        log.info("Starting burn-in export", extra={"project_id": self.project_id})

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clips = await repo.list_clips(self.project_id, self.user_id)
            log.info(
                "Clips loaded for burn-in",
                extra={"project_id": self.project_id, "clip_count": len(clips)},
            )

            from subtitle_styling.service import SubtitleStylingService
            styling = SubtitleStylingService()

            burned = []
            for clip in clips:
                if not clip.local_path or not Path(clip.local_path).exists():
                    log.warning(
                        "Clip skipped for burn-in: missing local file",
                        extra={"project_id": self.project_id, "clip_id": clip.id, "local_path": clip.local_path},
                    )
                    continue
                try:
                    log.info(
                        "Burning subtitles for clip",
                        extra={"project_id": self.project_id, "clip_id": clip.id, "title": clip.title},
                    )
                    burned_path = await styling.burn_subtitles(
                        video_path=clip.local_path,
                        clip_start=clip.start_time,
                        clip_end=clip.end_time,
                        title_text=clip.title,
                        enable_watermark=self.watermark_enabled,
                    )
                    burned.append({
                        "clip_id": clip.id,
                        "title": clip.title,
                        "burned_path": burned_path,
                    })
                    log.info(
                        "Burn-in success",
                        extra={"project_id": self.project_id, "clip_id": clip.id, "burned_path": burned_path},
                    )
                except Exception as exc:
                    log.warning(
                        "Burn-in failed for clip",
                        extra={
                            "project_id": self.project_id,
                            "clip_id": clip.id,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    )

        log.info(
            "Burn-in export complete",
            extra={"project_id": self.project_id, "burned_count": len(burned), "total_clips": len(clips)},
        )
        self._notify(f"Burned {len(burned)}/{len(clips)} clips", 100)
        return {"status": "completed", "burned_clips": burned, "message": "Titles burned at export time"}

    async def _mark_step_running(self, step: PipelineStepType) -> None:
        self._notify(f"Starting {step.value}...", 0)
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.update_step_status(state.id, step, StepStatus.RUNNING)
        except Exception as exc:
            log.debug(f"Failed to update step status to running: {exc}")

    async def _mark_step_completed(self, step: PipelineStepType, result: Any) -> None:
        self._notify(f"Completed {step.value}", 100)
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.update_step_status(state.id, step, StepStatus.COMPLETED)
        except Exception as exc:
            log.debug(f"Failed to update step status to completed: {exc}")

    async def _mark_step_failed(self, step: PipelineStepType, error: str) -> None:
        self._notify(f"Failed: {step.value} - {error}", 0)
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.update_step_status(state.id, step, StepStatus.FAILED, message=error)
        except Exception as exc:
            log.debug(f"Failed to update step status to failed: {exc}")

    async def _mark_pipeline_completed(self) -> None:
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                await repo.update_pipeline_current_step(self.project_id, PipelineStepType.BURN_IN_EXPORT, is_completed=True)
        except Exception as exc:
            log.error(f"Failed to mark pipeline completed: project={self.project_id} error={exc}")

    async def _mark_pipeline_failed(self, error: str) -> None:
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    state.error = error
                    state.is_completed = True
                    await repo._session.commit()
        except Exception as exc:
            log.error(f"Failed to mark pipeline failed: project={self.project_id} error={exc}")

    def _notify(self, message: str, percent: int) -> None:
        if self.progress_callback:
            try:
                result = self.progress_callback(message, percent, None)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                log.debug(f"Progress notify failed: {e}")

    async def _fetch_processed_bytes(self, url: str) -> bytes:
        log.info("Fetching processed bytes", extra={"project_id": self.project_id, "url": url})
        if url.startswith("processed://") or url.startswith("preview://"):
            return b""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
