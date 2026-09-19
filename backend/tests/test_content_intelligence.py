from __future__ import annotations

import pytest

from content_intelligence.classifier import ContentClassifier
from content_intelligence.highlighter import HighlightDetector
from content_intelligence.scorer import ClipScorer


class FakeOpenAI:
    async def chat(self, messages, **kwargs):
        raise RuntimeError("API unavailable")


@pytest.mark.asyncio
async def test_classifier_heuristic_gaming():
    classifier = ContentClassifier(FakeOpenAI())
    result = await classifier.classify(
        {"title": "Epic Minecraft Gameplay", "summary": "Playing Minecraft", "keywords": ["game", "minecraft"]},
        [],
    )
    assert result["category"] == "gaming"
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_classifier_heuristic_comedy():
    classifier = ContentClassifier(FakeOpenAI())
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


def _undiarized_transcript(count: int = 120, step: float = 4.4) -> list[dict]:
    """Whisper output with no speaker labels, which is the normal case.

    Diarization needs an HF token the deployment does not set, so every segment
    comes back without a `speaker` key.
    """
    lines = [
        "I finally bought the house and it cost ten million dollars.",
        "Let me show you the kitchen because the kitchen is insane.",
        "My mom cried when she walked in here for the first time.",
        "I almost lost everything last year and nobody knew about it.",
        "The secret is that I reinvested every single dollar.",
    ]
    return [
        {"start": round(i * step, 3), "end": round(i * step + step, 3), "text": lines[i % len(lines)]}
        for i in range(count)
    ]


class TestTranscriptFallback:
    """The fallback decides what the user sees when the model returns nothing."""

    def test_undiarized_transcript_yields_many_candidates(self):
        # Regression: grouping by speaker turned an undiarized transcript into a
        # single turn spanning the whole video, so the product shipped exactly
        # one clip per video no matter how long the source was.
        segments = _undiarized_transcript()
        duration = float(segments[-1]["end"])
        detector = HighlightDetector()

        candidates = detector._detect_from_transcript(segments, "vlog", duration, 20.0, 60.0)

        assert len(candidates) > 1
        assert all(not c.get("speakers") for c in candidates)

    def test_candidates_cover_the_whole_video(self):
        segments = _undiarized_transcript()
        duration = float(segments[-1]["end"])
        detector = HighlightDetector()

        candidates = detector._detect_from_transcript(segments, "vlog", duration, 20.0, 60.0)

        assert min(c["start_time"] for c in candidates) < duration * 0.2
        assert max(c["end_time"] for c in candidates) > duration * 0.8

    def test_single_speaker_label_does_not_collapse_output(self):
        segments = _undiarized_transcript()
        for segment in segments:
            segment["speaker"] = "Speaker 1"
        duration = float(segments[-1]["end"])
        detector = HighlightDetector()

        candidates = detector._detect_from_transcript(segments, "vlog", duration, 20.0, 60.0)

        assert len(candidates) > 1

    def test_empty_transcript_returns_nothing(self):
        detector = HighlightDetector()
        assert detector._detect_from_transcript([{"text": "  "}], "vlog", 100.0) == []


class TestDurationFitting:
    def test_short_moment_is_grown_not_dropped(self):
        # The model returns the right passage with the wrong length; dropping it
        # threw away good clips, and passing it through rendered 4-second files.
        segments = _undiarized_transcript()
        duration = float(segments[-1]["end"])
        detector = HighlightDetector()

        fitted = detector._fit_durations(
            [{"start_time": 100.0, "end_time": 104.4, "score": 0.9}],
            segments, duration, 20.0, 60.0,
        )

        assert len(fitted) == 1
        assert fitted[0]["end_time"] - fitted[0]["start_time"] >= 20.0

    def test_long_moment_is_trimmed_to_the_maximum(self):
        segments = _undiarized_transcript()
        duration = float(segments[-1]["end"])
        detector = HighlightDetector()

        fitted = detector._fit_durations(
            [{"start_time": 10.0, "end_time": 300.0, "score": 0.9}],
            segments, duration, 20.0, 60.0,
        )

        assert fitted[0]["end_time"] - fitted[0]["start_time"] <= 60.0

    def test_video_shorter_than_minimum_still_yields_a_clip(self):
        detector = HighlightDetector()
        fitted = detector._fit_durations(
            [{"start_time": 0.0, "end_time": 8.0, "score": 0.9}],
            [], 10.0, 20.0, 60.0,
        )
        assert len(fitted) == 1
        assert fitted[0]["end_time"] <= 10.0


class TestScoreNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [(0.85, 0.85), (8.5, 0.85), (85, 0.85), (100, 1.0), (-1, 0.0)],
    )
    def test_model_score_scales_are_rescaled(self, raw, expected):
        # Clamping instead of rescaling turned every 0-10 answer into 1.0 and
        # flattened the ranking the spread selection depends on.
        assert HighlightDetector._normalize_score(raw) == pytest.approx(expected, abs=0.01)

    def test_unparseable_score_uses_the_default(self):
        assert HighlightDetector._normalize_score("nonsense", default=0.5) == 0.5


class TestSpreadSelection:
    def test_tied_scores_are_spread_across_the_timeline(self):
        # Ranking by score alone returned the first N candidates whenever scores
        # tied, so clips all came from the opening minutes.
        candidates = [
            {"start_time": float(i * 40), "end_time": float(i * 40 + 30), "score": 0.5}
            for i in range(12)
        ]

        selected = HighlightDetector._select_spread(candidates, 4, duration=480.0)

        assert len(selected) == 4
        assert max(c["start_time"] for c in selected) > 240.0

    def test_higher_scores_still_win_within_a_region(self):
        candidates = [
            {"start_time": 0.0, "end_time": 30.0, "score": 0.2},
            {"start_time": 5.0, "end_time": 35.0, "score": 0.9},
            {"start_time": 400.0, "end_time": 430.0, "score": 0.4},
        ]

        selected = HighlightDetector._select_spread(candidates, 2, duration=460.0)

        assert {c["score"] for c in selected} == {0.9, 0.4}

    def test_never_returns_more_than_asked_for(self):
        candidates = [
            {"start_time": float(i * 30), "end_time": float(i * 30 + 25), "score": 0.5}
            for i in range(20)
        ]
        assert len(HighlightDetector._select_spread(candidates, 5, duration=600.0)) == 5


class TestClipCount:
    def test_long_video_allows_many_clips(self):
        assert HighlightDetector._max_clips(3600.0, 30.0) >= 20

    def test_short_video_still_gets_a_shelf_of_options(self):
        assert HighlightDetector._max_clips(120.0, 30.0) >= 5

    def test_explicit_setting_wins(self):
        assert HighlightDetector._max_clips(3600.0, 30.0, explicit=3) == 3
