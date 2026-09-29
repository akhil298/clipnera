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
from content_intelligence.director import VideoDirector
from visual_timeline import attach_scenes, describe_video
from content_intelligence.edit_plan import build_clips, build_story_clips, number_clips
from content_intelligence.highlighter import (
    MAX_CLIP_DURATION,
    MAX_CLIPS_PER_HOUR,
    MIN_CLIP_DURATION,
    HighlightDetector,
)
from content_intelligence.metadata_gen import MetadataGenerator
from content_intelligence.research import TopicResearcher
from content_intelligence.scorer import ClipScorer
from content_intelligence.sentences import Sentence, build_sentences, speaker_legend
from content_intelligence.signals import AudioSignals, extract_audio_signals
from video_processor.ffmpeg_service import FFmpegService

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

# Story clips (moments from across the video in one clip) take up to a quarter
# of a run's clips, and never more than this many.
MAX_STORY_CLIPS = 3
# Stitching lines from different parts of a news video risks changing what was
# said, so these categories only ever get single-moment clips.
NO_STORY_CATEGORIES = frozenset({"news_politics"})


def story_clip_count(settings: dict[str, Any], max_clips: int, category: str) -> int:
    """How many of a run's clips may be stories: none unless the run asked for them."""
    if settings.get("story_clips") is not True or category in NO_STORY_CATEGORIES or max_clips < 2:
        return 0
    return min(MAX_STORY_CLIPS, max(1, max_clips // 4))


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
        self._ffmpeg = FFmpegService()
        self._highlighter = HighlightDetector(get_text_client(is_pro=is_pro, step="highlight_detection"))
        self._scorer = ClipScorer()
        self._metadata_gen = MetadataGenerator(get_text_client(is_pro=is_pro, step="titles"))
        self._director = VideoDirector(
            get_text_client(is_pro=is_pro, step="map"),
            get_text_client(is_pro=is_pro, step="director"),
        )

    async def analyze_project(
        self,
        project_id: str,
        video_path: str,
        transcript_segments: list[dict],
        progress_callback: Callable[[str, int, str | None], None] | None = None,
        clip_settings: dict[str, Any] | None = None,
    ) -> dict:
        """Understand the video: what it is, its category, and where the moments are.

        One Map pass over a compact sentence table replaces the separate
        research, classification and frame-analysis calls. If it fails the old
        path runs, so a provider outage degrades the result instead of the run.
        """
        if progress_callback:
            await self._notify(progress_callback, "Listening for peaks and reactions...", 10)
        duration = await self._ffmpeg.probe_duration(video_path)
        audio, scenes = await asyncio.gather(extract_audio_signals(video_path), describe_video(video_path, duration))
        sentences = build_sentences(transcript_segments, audio)
        attach_scenes(sentences, scenes)

        if progress_callback:
            await self._notify(progress_callback, "Mapping the video...", 30)
        analysis: dict[str, Any] | None = None
        if sentences:
            try:
                target = 2 * HighlightDetector._max_clips(
                    duration,
                    float((clip_settings or {}).get("max_clips_per_hour") or MAX_CLIPS_PER_HOUR),
                    (clip_settings or {}).get("max_clips"),
                )
                video_map = await self._director.map(sentences, duration, speaker_legend(transcript_segments), target)
                analysis = self._analysis_from_map(video_map, audio, len(sentences))
            except Exception as exc:
                log.warning("Map pass failed, falling back to research + classification: %s", exc)

        if analysis is None:
            topic_research = await self._research_topic(video_path, transcript_segments)
            classification = await self._classifier.classify(topic_research, transcript_segments)
            analysis = {
                "topic_research": topic_research,
                "classification": classification,
                "frame_analysis": self._signal_summary(audio),
            }

        analysis["visual_timeline"] = scenes
        await self._persist_analysis(project_id, analysis)
        return analysis

    @staticmethod
    def _signal_summary(audio: AudioSignals | None) -> dict[str, Any]:
        return {"audio_peaks": audio.peaks() if audio else [], "scene_changes": [], "descriptions": {}}

    def _analysis_from_map(self, video_map: dict[str, Any], audio: AudioSignals | None, sentence_count: int) -> dict:
        topic_research = {
            "title": video_map.get("title", ""),
            "summary": video_map.get("summary", ""),
            "topics": video_map.get("topics", []),
            "entities": video_map.get("entities", []),
            "important_statements": [],
            "events": [],
            "key_moments": [c.get("why", "") for c in video_map.get("candidates", [])][:20],
            "context_required": [],
            "current_relevance": "",
            "research_queries": [],
            "sources": [],
            "research_method": "map_pass",
        }
        classification = {
            "category": video_map.get("category", "unknown"),
            "confidence": video_map.get("confidence", 0.5),
            "keywords": video_map.get("topics", []),
            "reasoning": "map pass",
        }
        log.info(
            "Map: category=%s, %d candidate(s) from %d sentence(s)",
            classification["category"], len(video_map.get("candidates", [])), sentence_count,
        )
        return {
            "topic_research": topic_research,
            "classification": classification,
            "frame_analysis": self._signal_summary(audio),
            "map": video_map,
        }

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
            await self._notify(progress_callback, "Directing the edit...", 50)

        highlights = await self._direct(video_path, transcript_segments, analysis, clip_settings or {})
        if not highlights:
            if progress_callback:
                await self._notify(progress_callback, "Detecting highlight segments...", 55)
            highlights = await self._highlighter.detect(
                video_path=video_path,
                transcript_segments=transcript_segments,
                analysis=analysis,
                clip_settings=clip_settings,
            )

        if progress_callback:
            await self._notify(progress_callback, f"Found {len(highlights)} clip(s)", 65)

        return highlights

    async def _direct(
        self, video_path: str, transcript_segments: list[dict], analysis: dict, settings: dict[str, Any],
    ) -> list[dict]:
        """Edit plans from the director, or [] when there is no map or it fails."""
        video_map = analysis.get("map") if isinstance(analysis, dict) else None
        if not video_map or not video_map.get("candidates"):
            return []
        duration = await self._ffmpeg.probe_duration(video_path)
        min_seconds = float(settings.get("min_clip_duration") or MIN_CLIP_DURATION)
        max_seconds = float(settings.get("max_clip_duration") or MAX_CLIP_DURATION)
        max_clips = HighlightDetector._max_clips(
            duration, float(settings.get("max_clips_per_hour") or MAX_CLIPS_PER_HOUR), settings.get("max_clips"),
        )
        # Rebuilt rather than stored: the table with word timings is large, and
        # rebuilding it from the transcript is instant. Loudness flags only
        # matter to the models, which already read them in the Map pass.
        sentences = build_sentences(transcript_segments, None)
        attach_scenes(sentences, analysis.get("visual_timeline") or [])
        category = str(video_map.get("category") or "unknown")
        jump_cuts = bool(settings.get("jump_cuts", True))
        story_count = story_clip_count(settings, max_clips, category)
        plans, stories = await asyncio.gather(
            self._director.direct(sentences, video_map, max_clips, min_seconds, max_seconds),
            self._stories(sentences, video_map, story_count, duration, min_seconds, max_seconds, category, jump_cuts),
            return_exceptions=True,
        )
        if isinstance(plans, BaseException):
            log.warning("Director pass failed, falling back to highlight detection: %s", plans)
            return []
        if isinstance(stories, BaseException):
            log.warning("Story pass failed; this run gets moment clips only: %s", stories)
            stories = []
        clips = build_clips(
            plans, sentences, duration, min_seconds, max_seconds, max_clips - len(stories),
            category=category, jump_cuts=jump_cuts,
        )
        return number_clips(clips + stories) if clips else []

    async def _stories(
        self,
        sentences: list[Sentence],
        video_map: dict[str, Any],
        count: int,
        duration: float,
        min_seconds: float,
        max_seconds: float,
        category: str,
        jump_cuts: bool,
    ) -> list[dict]:
        """Story clips that passed the viewer check, at most ``count``.

        One spare is planned so a clip the check refuses can be replaced.
        """
        if not count:
            return []
        plans = await self._director.story(sentences, video_map, count + 1, min_seconds, max_seconds)
        clips = build_story_clips(
            plans, sentences, duration, min_seconds, max_seconds, count + 1, category, jump_cuts,
        )
        verdicts = await self._director.check([clip["transcript_excerpt"] for clip in clips])
        return [clip for clip, ok in zip(clips, verdicts) if ok][:count]

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
