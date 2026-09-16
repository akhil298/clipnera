from __future__ import annotations

import asyncio
import json
from typing import Any, Callable
from uuid import uuid4

from clients.ai.groq import Groq
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from content_intelligence.analyzer import FrameAnalyzer
from content_intelligence.classifier import ContentClassifier
from content_intelligence.highlighter import HighlightDetector
from content_intelligence.metadata_gen import MetadataGenerator
from content_intelligence.reframing import build_smart_output_formats
from content_intelligence.research import TopicResearcher
from content_intelligence.scorer import ClipScorer

log = get_logger(__name__)


class ContentIntelligenceService:
    def __init__(self) -> None:
        self._groq = Groq()
        self._researcher = TopicResearcher(self._groq)
        self._classifier = ContentClassifier(self._groq)
        self._analyzer = FrameAnalyzer()
        self._highlighter = HighlightDetector(self._groq)
        self._scorer = ClipScorer()
        self._metadata_gen = MetadataGenerator(self._groq)

    async def analyze_project(
        self,
        project_id: str,
        video_path: str,
        transcript_segments: list[dict],
        progress_callback: Callable[[str, int, str | None], None] | None = None,
    ) -> dict:
        if progress_callback:
            await self._notify(progress_callback, "Researching topic...", 10)

        topic_research = await self._research_topic(video_path, transcript_segments)

        if progress_callback:
            await self._notify(progress_callback, "Classifying content category...", 20)

        classification = await self._classifier.classify(topic_research, transcript_segments)

        if progress_callback:
            await self._notify(progress_callback, "Analyzing video frames...", 30)

        frame_analysis = await self._analyzer.analyze(video_path, classification.get("category", "unknown"))

        analysis = {
            "topic_research": topic_research,
            "classification": classification,
            "frame_analysis": frame_analysis,
        }

        await self._persist_analysis(project_id, analysis)
        return analysis

    async def detect_highlights(
        self,
        project_id: str,
        video_path: str,
        transcript_segments: list[dict],
        analysis: dict,
        progress_callback: Callable[[str, int, str | None], None] | None = None,
        clip_settings: dict[str, Any] | None = None,
    ) -> list[dict]:
        if progress_callback:
            await self._notify(progress_callback, "Detecting highlight segments...", 50)

        highlights = await self._highlighter.detect(
            video_path=video_path,
            transcript_segments=transcript_segments,
            analysis=analysis,
            clip_settings=clip_settings,
        )

        if progress_callback:
            await self._notify(progress_callback, f"Found {len(highlights)} candidate segments", 65)

        return highlights

    async def score_highlights(self, highlights: list[dict], analysis: dict, clip_settings: dict[str, Any] | None = None) -> list[dict]:
        return await self._scorer.score(highlights, analysis, clip_settings=clip_settings)

    async def generate_metadata_for_clips(self, clips: list[dict]) -> list[dict]:
        return await self._metadata_gen.generate_batch(clips)

    async def analyze_candidate_clips(
        self,
        video_path: str,
        clips: list[dict],
        max_frames_per_clip: int = 8,
        frame_interval: float = 2.0,
    ) -> dict[str, list[dict]]:
        return await self._analyzer.analyze_candidate_clips(
            video_path,
            clips,
            max_frames_per_clip=max_frames_per_clip,
            frame_interval=frame_interval,
        )

    async def build_smart_output_formats(
        self,
        frame_analyses: list[dict],
        source_width: int,
        source_height: int,
        aspect_ratios: list[str] | None = None,
        content_category: str = "unknown",
        transcript_segments: list[dict[str, Any]] | None = None,
        scene_changes: list[float] | None = None,
        video_path: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        ratios = aspect_ratios or self.default_aspect_ratios()
        return await build_smart_output_formats(
            frame_analyses=frame_analyses,
            source_width=source_width,
            source_height=source_height,
            aspect_ratios=ratios,
            content_category=content_category,
            transcript_segments=transcript_segments,
            scene_changes=scene_changes,
            video_path=video_path,
        )

    async def build_output_formats(
        self,
        frame_analyses: list[dict[str, Any]],
        source_width: int,
        source_height: int,
        aspect_ratios: list[str] | None = None,
        content_category: str = "unknown",
        transcript_segments: list[dict[str, Any]] | None = None,
        scene_changes: list[float] | None = None,
        video_path: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        return await self.build_smart_output_formats(
            frame_analyses=frame_analyses,
            source_width=source_width,
            source_height=source_height,
            aspect_ratios=aspect_ratios,
            content_category=content_category,
            transcript_segments=transcript_segments,
            scene_changes=scene_changes,
            video_path=video_path,
        )

    def analyze_layouts(
        self,
        frame_analyses: list[dict[str, Any]],
        scene_changes: list[float] | None = None,
        content_category: str = "unknown",
    ) -> list[dict[str, Any]]:
        try:
            from content_intelligence.layout_analyzer import LayoutAnalyzer
        except Exception as exc:
            log.warning("LayoutAnalyzer unavailable: %s", exc)
            return []
        analyzer = LayoutAnalyzer()
        decisions = analyzer.analyze_scenes(
            frames=frame_analyses,
            scene_changes=scene_changes,
            content_category=content_category,
        )
        return [
            {
                "layout": d.layout,
                "confidence": d.confidence,
                "scene_start": d.scene_start,
                "scene_end": d.scene_end,
                "evidence": d.evidence,
            }
            for d in decisions
        ]

    @staticmethod
    def default_aspect_ratios() -> list[str]:
        from core.config import get_settings

        raw = getattr(get_settings(), "DEFAULT_OUTPUT_ASPECT_RATIOS", "9:16,1:1,4:5,16:9")
        return [item.strip() for item in raw.split(",") if item.strip()]

    async def _research_topic(self, video_path: str, transcript_segments: list[dict]) -> dict:
        return await self._researcher.research(video_path, transcript_segments)

    async def _persist_analysis(self, project_id: str, analysis: dict) -> None:
        try:
            from clip_generation.model import VideoAnalysis
            from sqlalchemy import insert

            frame_analysis = analysis.get("frame_analysis", {})
            topic_research = analysis.get("topic_research", {})
            classification = analysis.get("classification", {})
            async with AsyncSessionLocal() as session:
                stmt = insert(VideoAnalysis).values(
                    id=str(uuid4()),
                    project_id=project_id,
                    content_category=classification.get("category"),
                    category_confidence=classification.get("confidence"),
                    topic_keywords=json.dumps(topic_research.get("topics", []), ensure_ascii=False),
                    scene_changes=json.dumps(frame_analysis.get("scene_changes", [])),
                    frame_descriptions=json.dumps(frame_analysis.get("descriptions", {}), ensure_ascii=False),
                    transcript_summary=json.dumps({
                        "summary": topic_research.get("summary", ""),
                        "entities": topic_research.get("entities", []),
                        "events": topic_research.get("events", []),
                        "key_moments": topic_research.get("key_moments", []),
                        "context_required": topic_research.get("context_required", []),
                        "current_relevance": topic_research.get("current_relevance", ""),
                    }, ensure_ascii=False),
                    analysis_json=json.dumps(analysis, ensure_ascii=False, default=str),
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as exc:
            log.warning(f"Failed to persist analysis: {exc}")

    async def _notify(self, cb, message: str, percent: int) -> None:
        if cb:
            try:
                result = cb(message, percent, None)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log.debug(f"Progress notify failed: {exc}")
