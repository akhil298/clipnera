from __future__ import annotations

import pytest

from content_intelligence.word_snapper import snap_clip_to_sentences, snap_clip_to_segments, snap_clip_to_words


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


class TestSnapClipToSentences:
    # The transcript behind a clip that opened on "Not for one hour" and
    # stopped on the setup line before its payoff.
    @pytest.fixture
    def segments(self):
        return [
            {"start": 19.64, "end": 23.64, "text": "Imagine speaking English before anything else."},
            {"start": 24.04, "end": 27.68, "text": "Not for one hour, just five minutes."},
            {"start": 27.68, "end": 32.08, "text": "It sounds too simple,"},
            {"start": 32.52, "end": 35.60, "text": "but that is why most people never try it."},
            {"start": 35.60, "end": 38.04, "text": "Minute one, talk about what you see"},
            {"start": 38.64, "end": 41.00, "text": "around your room."},
        ]

    def test_start_mid_sentence_moves_to_sentence_start(self, segments):
        start, _ = snap_clip_to_sentences(33.0, 41.0, segments)
        assert start == 27.68

    def test_continuation_opener_takes_previous_sentence(self, segments):
        start, _ = snap_clip_to_sentences(24.04, 32.08, segments)
        assert start == 19.64

    def test_end_mid_sentence_extends_to_sentence_end(self, segments):
        _, end = snap_clip_to_sentences(27.68, 36.0, segments)
        assert end == 41.0

    def test_overrun_pulls_end_back_to_last_fitting_sentence(self, segments):
        start, end = snap_clip_to_sentences(27.68, 36.0, segments, max_duration=10.0)
        assert (start, end) == (27.68, 35.6)

    def test_unpunctuated_transcript_is_left_alone(self):
        segments = [
            {"start": 0.0, "end": 4.0, "text": "no punctuation here"},
            {"start": 4.0, "end": 8.0, "text": "or here either"},
        ]
        assert snap_clip_to_sentences(2.0, 6.0, segments) == (2.0, 6.0)
