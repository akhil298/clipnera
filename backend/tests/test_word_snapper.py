from __future__ import annotations

import pytest

from content_intelligence.word_snapper import snap_clip_to_words, snap_clip_to_segments


class TestSnapClipToWords:
    @pytest.fixture
    def words(self):
        return [
            {"start": 0.0, "end": 0.5, "text": "Hello"},
            {"start": 1.0, "end": 1.5, "text": "world"},
            {"start": 3.0, "end": 3.5, "text": "how"},
            {"start": 3.5, "end": 4.0, "text": "are"},
            {"start": 4.0, "end": 4.5, "text": "you"},
        ]

    def test_snaps_to_nearest_word_start(self, words):
        result = snap_clip_to_words(1.2, 4.2, words, 10.0)
        assert result[0] <= 1.0
        assert result[1] >= 4.0

    def test_lead_in_to_silence(self, words):
        result = snap_clip_to_words(0.1, 4.5, words, 10.0)
        assert result[0] >= 0.0

    def test_tail_into_silence(self, words):
        result = snap_clip_to_words(0.0, 4.6, words, 10.0)
        assert result[1] <= 5.0

    def test_min_duration_enforced(self, words):
        result = snap_clip_to_words(0.0, 0.5, words, 10.0, min_duration=3.0)
        assert result[1] - result[0] >= 3.0 or result == (0.0, 0.5)

    def test_max_duration_enforced(self, words):
        result = snap_clip_to_words(0.0, 10.0, words, 10.0, max_duration=2.0)
        assert result[1] - result[0] <= 2.0

    def test_fallback_on_short_result(self, words):
        result = snap_clip_to_words(0.0, 0.1, words, 10.0, min_duration=20.0)
        assert result == (0.0, 0.1)

    def test_empty_words_fallback(self):
        result = snap_clip_to_words(0.0, 5.0, [], 10.0)
        assert result == (0.0, 5.0)

    def test_words_from_segments(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello", "words": [
                {"start": 0.1, "end": 0.5, "word": "Hello"},
                {"start": 0.6, "end": 1.0, "word": "world"},
            ]},
            {"start": 3.0, "end": 5.0, "text": "Test", "words": [
                {"start": 3.1, "end": 3.5, "word": "Test"},
            ]},
        ]
        result = snap_clip_to_words(0.2, 3.5, segments, 10.0)
        assert result[0] >= 0.0
        assert result[1] <= 4.0

    def test_negative_times_clamped(self, words):
        result = snap_clip_to_words(-5.0, -2.0, words, 10.0)
        assert result[0] >= 0.0


class TestSnapClipToSegments:
    @pytest.fixture
    def segments(self):
        return [
            {"start": 0.0, "end": 5.0, "text": "First segment"},
            {"start": 6.0, "end": 10.0, "text": "Second segment"},
            {"start": 15.0, "end": 20.0, "text": "Third segment"},
        ]

    def test_snaps_to_segment_boundaries(self, segments):
        result = snap_clip_to_segments(5.5, 15.5, segments, 25.0)
        assert result[0] >= 0.0
        assert result[1] <= 20.0

    def test_empty_segments(self):
        result = snap_clip_to_segments(0.0, 5.0, [], 10.0)
        assert result == (0.0, 5.0)

    def test_short_result_fallback(self, segments):
        result = snap_clip_to_segments(0.0, 1.0, segments, 25.0, min_duration=10.0)
        assert result == (0.0, 1.0)
