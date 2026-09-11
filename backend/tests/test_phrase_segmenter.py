from __future__ import annotations

import pytest

from subtitle_styling.phrase_segmenter import segment_phrases, segment_for_captions


class TestSegmentPhrases:
    def test_basic_segmentation(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Hello world."},
            {"start": 2.0, "end": 3.0, "text": "This is a test."},
            {"start": 5.0, "end": 6.0, "text": "More content here."},
        ]
        result = segment_phrases(segments, min_duration=1.0, max_gap=1.0)
        assert len(result) >= 1
        for phrase in result:
            assert "start_time" in phrase
            assert "end_time" in phrase
            assert "text" in phrase

    def test_large_gap_splits_phrases(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Hello world."},
            {"start": 10.0, "end": 11.0, "text": "This is a test."},
        ]
        result = segment_phrases(segments, min_duration=0.5, max_gap=1.0, pad=0.0)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world."
        assert result[1]["text"] == "This is a test."

    def test_padding_applied(self):
        segments = [
            {"start": 2.0, "end": 3.0, "text": "Hello world."},
        ]
        result = segment_phrases(segments, min_duration=0.5, max_gap=1.0, pad=0.08)
        assert result[0]["start_time"] == pytest.approx(1.92, abs=0.01)

    def test_pad_does_not_make_negative(self):
        segments = [
            {"start": 0.1, "end": 1.0, "text": "Hi."},
        ]
        result = segment_phrases(segments, min_duration=0.5, max_gap=1.0, pad=0.5)
        assert result[0]["start_time"] >= 0.0

    def test_sentence_boundary_split(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "First sentence."},
            {"start": 1.2, "end": 2.0, "text": "Second sentence!"},
        ]
        result = segment_phrases(segments, min_duration=0.5, max_gap=0.5)
        assert len(result) >= 2
        assert "First sentence" in result[0]["text"]
        assert "Second sentence" in result[1]["text"]

    def test_min_duration_filter(self):
        segments = [
            {"start": 0.0, "end": 0.1, "text": "Hi."},
        ]
        result = segment_phrases(segments, min_duration=0.5, max_gap=1.0)
        assert len(result) == 1
        assert result[0]["text"] == "Hi."

    def test_empty_segments(self):
        result = segment_phrases([])
        assert result == []

    def test_word_extraction_from_nested(self):
        segments = [
            {
                "start": 0.0, "end": 3.0,
                "text": "Hello world",
                "words": [
                    {"start": 0.1, "end": 0.5, "word": "Hello"},
                    {"start": 0.6, "end": 1.0, "word": "world"},
                    {"start": 2.0, "end": 2.5, "word": "test"},
                ],
            },
        ]
        result = segment_phrases(segments, min_duration=1.0, max_gap=1.0)
        assert len(result) == 1
        assert "Hello" in result[0]["text"]
        assert "test" in result[0]["text"]


class TestSegmentForCaptions:
    def test_basic_segmentation(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Hello world"},
            {"start": 1.0, "end": 2.0, "text": "this is a test"},
        ]
        result = segment_for_captions(segments, max_chars=20, max_words_per_line=4)
        assert len(result) >= 1
        for seg in result:
            assert seg["start_time"] >= 0
            assert seg["end_time"] > seg["start_time"]
            assert seg["text"].strip()

    def test_max_words_per_line(self):
        segments = [
            {"start": 0.0, "end": 5.0, "text": "one two three four five six seven"},
        ]
        result = segment_for_captions(segments, max_chars=100, max_words_per_line=3)
        assert len(result) >= 2

    def test_sentence_break(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Hello world."},
            {"start": 1.1, "end": 2.0, "text": "Next sentence here."},
        ]
        result = segment_for_captions(segments, max_chars=100)
        texts = [s["text"] for s in result]
        assert any("Hello" in t for t in texts)
        assert any("Next" in t for t in texts)

    def test_empty_segments(self):
        result = segment_for_captions([])
        assert result == []
