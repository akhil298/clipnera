from __future__ import annotations

import pytest

from content_intelligence.classifier import ContentClassifier
from content_intelligence.highlighter import HighlightDetector
from content_intelligence.scorer import ClipScorer


class FakeOpenAI:
    async def chat(self, messages, **kwargs):
        raise RuntimeError("API unavailable")


class FakeGemini:
    pass


@pytest.mark.asyncio
async def test_classifier_heuristic_gaming():
    classifier = ContentClassifier(FakeOpenAI(), FakeGemini())
    result = await classifier.classify(
        {"title": "Epic Minecraft Gameplay", "summary": "Playing Minecraft", "keywords": ["game", "minecraft"]},
        [],
    )
    assert result["category"] == "gaming"
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_classifier_heuristic_comedy():
    classifier = ContentClassifier(FakeOpenAI(), FakeGemini())
    result = await classifier.classify(
        {"title": "Funniest Moments Compilation", "summary": "Hilarious clips", "keywords": ["funny", "hilarious"]},
        [],
    )
    assert result["category"] == "comedy"


@pytest.mark.asyncio
async def test_highlighter_merge_overlapping():
    detector = HighlightDetector()
    candidates = [
        {"start_time": 0.0, "end_time": 30.0, "score": 0.5, "reasons": ["a"]},
        {"start_time": 25.0, "end_time": 50.0, "score": 0.3, "reasons": ["b"]},
        {"start_time": 55.0, "end_time": 80.0, "score": 0.2, "reasons": ["c"]},
    ]
    merged = detector._merge_overlapping(candidates, 20.0)
    assert len(merged) == 2
    assert merged[0]["end_time"] >= 50.0
    assert merged[1]["start_time"] >= 50.0


@pytest.mark.asyncio
async def test_scorer_returns_sorted():
    scorer = ClipScorer()
    highlights = [
        {"start_time": 0.0, "end_time": 30.0, "score": 0.2, "transcript_excerpt": "hello world", "reasons": [], "content_category": "unknown"},
        {"start_time": 35.0, "end_time": 65.0, "score": 0.5, "transcript_excerpt": "this is a secret hack that will change your life", "reasons": ["signal"], "content_category": "tutorial_educational"},
    ]
    analysis = {"classification": {"category": "tutorial_educational"}}
    scored = await scorer.score(highlights, analysis)
    assert scored[0]["score"] >= scored[1]["score"]
    assert all(10.0 <= s["score"] <= 99.0 for s in scored)
