from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional
from core.database import AsyncSessionLocal
from clients.ai.gemini import Gemini
from clients.ai.groq import Groq
from core.logging_config import get_logger
from core.exceptions import CustomException
from content_intelligence.classifier import ContentClassifier
from content_intelligence.analyzer import FrameAnalyzer
from content_intelligence.highlighter import HighlightDetector
from content_intelligence.scorer import ClipScorer
from content_intelligence.metadata_gen import MetadataGenerator

log = get_logger(__name__)


class ContentIntelligenceService:
    def __init__(self) -> None:
        self._gemini = Gemini()
        self._grok = Groq()
        self._classifier = ContentClassifier(self._grok, self._gemini)
        self._analyzer = FrameAnalyzer(self._gemini)
        self._highlighter = HighlightDetector()
        self._scorer = ClipScorer()
        self._metadata_gen = MetadataGenerator(self._grok)

    async def analyze_project(self, project_id: str, video_path: str, transcript_segments: list[dict], progress_callback: Callable[[str, int, str | None], None] | None = None) -> dict:
        if progress_callback:
            await self._notify(progress_callback, "Researching topic...", 10)

        topic_research = await self._research_topic(video_path)

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

    async def detect_highlights(self, project_id: str, video_path: str, transcript_segments: list[dict], analysis: dict, progress_callback: Callable[[str, int, str | None], None] | None = None) -> list[dict]:
        if progress_callback:
            await self._notify(progress_callback, "Detecting highlight segments...", 50)

        highlights = await self._highlighter.detect(
            video_path=video_path,
            transcript_segments=transcript_segments,
            analysis=analysis,
        )

        if progress_callback:
            await self._notify(progress_callback, f"Found {len(highlights)} candidate segments", 65)

        return highlights

    async def score_highlights(self, highlights: list[dict], analysis: dict) -> list[dict]:
        return await self._scorer.score(highlights, analysis)

    async def generate_metadata_for_clips(self, clips: list[dict]) -> list[dict]:
        return await self._metadata_gen.generate_batch(clips)

    async def _research_topic(self, video_path: str) -> dict:
        filename = Path(video_path).stem
        return {
            "title": filename,
            "keywords": [],
            "summary": "",
        }

    async def _persist_analysis(self, project_id: str, analysis: dict) -> None:
        try:
            from clip_generation.model import VideoAnalysis
            from sqlalchemy import insert
            async with AsyncSessionLocal() as session:
                stmt = insert(VideoAnalysis).values(
                    id=str(__import__("uuid").uuid4()),
                    project_id=project_id,
                    content_category=analysis.get("classification", {}).get("category"),
                    category_confidence=analysis.get("classification", {}).get("confidence"),
                    topic_keywords=json.dumps(analysis.get("topic_research", {}).get("keywords", [])),
                    scene_changes=json.dumps(analysis.get("frame_analysis", {}).get("scene_changes", [])),
                    frame_descriptions=json.dumps(analysis.get("frame_analysis", {}).get("descriptions", {})),
                    transcript_summary=analysis.get("topic_research", {}).get("summary"),
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
            except Exception as e:
                log.debug(f"Progress notify failed: {e}")
