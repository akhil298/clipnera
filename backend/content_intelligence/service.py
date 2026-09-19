from __future__ import annotations

import asyncio
import json
from typing import Any, Callable
from uuid import uuid4

from clients.ai import get_text_client
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from content_intelligence.analyzer import FrameAnalyzer
from content_intelligence.classifier import ContentClassifier
from content_intelligence.highlighter import HighlightDetector
from content_intelligence.metadata_gen import MetadataGenerator
from content_intelligence.research import TopicResearcher
from content_intelligence.scorer import ClipScorer

log = get_logger(__name__)

# Which shapes each kind of content is actually posted in. Rendering every
# supported ratio for every clip quadrupled encode time to produce files nobody
# asked for, so a clip is now cut only in the shapes its category is published
# in. Categories absent here fall back to ``FALLBACK_ASPECT_RATIOS``.
CATEGORY_ASPECT_RATIOS: dict[str, tuple[str, ...]] = {
    # Shorts-native: 16:9 gameplay does not survive a square crop.
    "gaming": ("9:16",),
    # Talking heads read well in the square feed as well as vertical.
    "podcast_interview": ("9:16", "1:1"),
    "news_politics": ("9:16", "1:1"),
    # Long-form audiences are on YouTube, so landscape earns its render.
    "tutorial_educational": ("9:16", "16:9"),
    "tech": ("9:16", "16:9"),
    "music": ("9:16", "16:9"),
    "sports": ("9:16", "16:9"),
    # 4:5 is the tallest shape the Instagram feed allows.
    "fitness_health": ("9:16", "4:5"),
    "food": ("9:16", "4:5"),
    # Pure short-form.
    "comedy": ("9:16",),
    "reaction": ("9:16",),
    "vlog": ("9:16",),
    "unknown": ("9:16",),
}

FALLBACK_ASPECT_RATIOS: tuple[str, ...] = ("9:16",)


class ContentIntelligenceService:
    def __init__(self, is_pro: bool = False) -> None:
        # One client per step, not per service: STEP_POLICY pins the mechanical
        # steps to the free provider whatever the user pays, so spend lands on
        # the calls where being right actually matters. AI_PROVIDER can pin
        # everything to one provider for local work and A/B runs.
        self._is_pro = is_pro
        self._researcher = TopicResearcher(get_text_client(is_pro=is_pro, step="topic_research"))
        self._classifier = ContentClassifier(get_text_client(is_pro=is_pro, step="classification"))
        self._analyzer = FrameAnalyzer()
        self._highlighter = HighlightDetector(get_text_client(is_pro=is_pro, step="highlight_detection"))
        self._scorer = ClipScorer()
        self._metadata_gen = MetadataGenerator(
            get_text_client(is_pro=is_pro, step="titles"),
            cue_client=get_text_client(is_pro=is_pro, step="emoji_cues"),
        )

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

    @property
    def is_pro(self) -> bool:
        return self._is_pro

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

    @staticmethod
    def default_aspect_ratios(content_category: str | None = None) -> list[str]:
        """Shapes to render when the caller did not name any.

        ``DEFAULT_OUTPUT_ASPECT_RATIOS`` still wins when a deployment sets it,
        which is what pins a machine to one shape for local work and A/B runs.
        Left unset, the category decides, so a gaming clip is not also cut
        square and landscape for nobody.
        """
        from core.config import get_settings

        raw = (getattr(get_settings(), "DEFAULT_OUTPUT_ASPECT_RATIOS", "") or "").strip()
        if raw:
            configured = [item.strip() for item in raw.split(",") if item.strip()]
            if configured:
                return configured

        category = (content_category or "unknown").strip().lower()
        return list(CATEGORY_ASPECT_RATIOS.get(category, FALLBACK_ASPECT_RATIOS))

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
