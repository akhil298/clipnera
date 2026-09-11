from __future__ import annotations

import pytest

from content_intelligence.scorer import ClipScorer, ENGAGEMENT_SIGNALS


class TestClipScorer:
    @pytest.fixture
    def scorer(self):
        return ClipScorer()

    @pytest.fixture
    def analysis(self):
        return {"classification": {"category": "gaming"}}

    @pytest.fixture
    def highlights(self):
        return [
            {
                "start_time": 10.0,
                "end_time": 30.0,
                "transcript_excerpt": "This is the best gaming strategy ever! You won't believe this secret hack.",
                "score": 0.8,
                "reasons": ["keyword_match", "engagement"],
            },
            {
                "start_time": 40.0,
                "end_time": 55.0,
                "transcript_excerpt": "Regular content here",
                "score": 0.3,
                "reasons": ["scene_boundary"],
            },
        ]

    @pytest.mark.asyncio
    async def test_score_returns_list(self, scorer, highlights, analysis):
        result = await scorer.score(highlights, analysis)
        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_score_sorted_descending(self, scorer, highlights, analysis):
        result = await scorer.score(highlights, analysis)
        assert result[0]["score"] >= result[1]["score"]

    @pytest.mark.asyncio
    async def test_score_has_virality_scores(self, scorer, highlights, analysis):
        result = await scorer.score(highlights, analysis)
        for item in result:
            factors = item.get("scoring_factors", {})
            assert "virality_scores" in factors
            vs = factors["virality_scores"]
            assert "hook_score" in vs
            assert "engagement_score" in vs
            assert "value_score" in vs
            assert "shareability_score" in vs
            assert "virality_score" in vs

    @pytest.mark.asyncio
    async def test_virality_scores_bounded(self, scorer, highlights, analysis):
        result = await scorer.score(highlights, analysis)
        for item in result:
            vs = item["scoring_factors"]["virality_scores"]
            assert vs["hook_score"] <= 25.0
            assert vs["engagement_score"] <= 25.0
            assert vs["value_score"] <= 25.0
            assert vs["shareability_score"] <= 25.0
            assert vs["virality_score"] <= 100.0

    @pytest.mark.asyncio
    async def test_hook_score_engagement_signals(self, scorer, highlights, analysis):
        result = await scorer.score(highlights, analysis)
        first = result[0]
        vs = first["scoring_factors"]["virality_scores"]
        assert vs["hook_score"] > 0.0

    @pytest.mark.asyncio
    async def test_engagement_score_emotional_words(self, scorer, analysis):
        highlights = [{
            "start_time": 0.0,
            "end_time": 20.0,
            "transcript_excerpt": "amazing incredible scary",
            "score": 0.5,
            "reasons": [],
        }]
        result = await scorer.score(highlights, analysis)
        vs = result[0]["scoring_factors"]["virality_scores"]
        assert vs["engagement_score"] > 0.0

    @pytest.mark.asyncio
    async def test_value_score_fact_signals(self, scorer, analysis):
        highlights = [{
            "start_time": 0.0,
            "end_time": 20.0,
            "transcript_excerpt": "according to study data fact",
            "score": 0.5,
            "reasons": [],
        }]
        result = await scorer.score(highlights, analysis)
        vs = result[0]["scoring_factors"]["virality_scores"]
        assert vs["value_score"] > 0.0

    @pytest.mark.asyncio
    async def test_shareability_trending_signals(self, scorer, analysis):
        highlights = [{
            "start_time": 0.0,
            "end_time": 20.0,
            "transcript_excerpt": "trending viral share like",
            "score": 0.5,
            "reasons": [],
        }]
        result = await scorer.score(highlights, analysis)
        vs = result[0]["scoring_factors"]["virality_scores"]
        assert vs["shareability_score"] > 0.0

    @pytest.mark.asyncio
    async def test_category_engagement_factor(self, scorer):
        gaming_analysis = {"classification": {"category": "gaming"}}
        unknown_analysis = {"classification": {"category": "unknown"}}
        highlights = [{
            "start_time": 0.0,
            "end_time": 20.0,
            "transcript_excerpt": "test content here",
            "score": 0.5,
            "reasons": [],
        }]
        gaming_result = await scorer.score(highlights, gaming_analysis)
        unknown_result = await scorer.score(highlights, unknown_analysis)
        assert gaming_result[0]["scoring_factors"]["engagement_factor"] == 1.3
        assert unknown_result[0]["scoring_factors"]["engagement_factor"] == 0.8

    @pytest.mark.asyncio
    async def test_empty_highlights(self, scorer, analysis):
        result = await scorer.score([], analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_score_score_clamped(self, scorer, analysis):
        highlights = [{
            "start_time": 0.0,
            "end_time": 20.0,
            "transcript_excerpt": "wow amazing incredible",
            "score": 1.0,
            "reasons": ["a", "b", "c", "d"],
        }]
        result = await scorer.score(highlights, analysis)
        assert result[0]["score"] <= 99.0
        assert result[0]["score"] >= 10.0
