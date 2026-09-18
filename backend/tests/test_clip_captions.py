"""The clip transcript slice and its clip-relative caption projection.

These cover the sync contract between the two: `_clip_transcript` keeps source
(absolute) timestamps because the ASS generator rebases them itself, while
`_clip_captions` is what a player consumes and must start at zero.
"""

from __future__ import annotations

from clip_generation.service import ClipService

SEGMENTS = [
    {
        "start": 100.0,
        "end": 103.0,
        "text": "we made money fast",
        "speaker": "A",
        "words": [
            {"start": 100.0, "end": 100.4, "word": "we"},
            {"start": 100.4, "end": 101.0, "word": "made"},
            {"start": 101.0, "end": 102.0, "word": "money"},
            {"start": 102.0, "end": 103.0, "word": "fast"},
        ],
    },
    {
        "start": 108.0,
        "end": 110.0,
        "text": "then everything changed",
        "speaker": "A",
        "words": [
            {"start": 108.0, "end": 108.8, "word": "then"},
            {"start": 108.8, "end": 109.4, "word": "everything"},
            {"start": 109.4, "end": 110.0, "word": "changed"},
        ],
    },
    {"start": 200.0, "end": 202.0, "text": "unrelated tail", "speaker": "B"},
]


class TestClipTranscript:
    def test_keeps_absolute_timestamps(self):
        sliced = ClipService._clip_transcript(SEGMENTS, 99.0, 111.0)
        assert [s["start"] for s in sliced] == [100.0, 108.0]

    def test_preserves_word_timings(self):
        sliced = ClipService._clip_transcript(SEGMENTS, 99.0, 111.0)
        assert sliced[0]["words"][2] == {"start": 101.0, "end": 102.0, "word": "money"}

    def test_excludes_segments_outside_the_clip(self):
        sliced = ClipService._clip_transcript(SEGMENTS, 99.0, 104.0)
        assert len(sliced) == 1

    def test_drops_words_outside_the_clip(self):
        sliced = ClipService._clip_transcript(SEGMENTS, 99.0, 101.5)
        assert [w["word"] for w in sliced[0]["words"]] == ["we", "made", "money"]

    def test_keeps_speaker(self):
        sliced = ClipService._clip_transcript(SEGMENTS, 99.0, 111.0)
        assert sliced[0]["speaker"] == "A"


class TestClipCaptions:
    def test_rebases_onto_the_clip_timeline(self):
        transcript = ClipService._clip_transcript(SEGMENTS, 100.0, 110.0)
        captions = ClipService._clip_captions(transcript, 100.0, 110.0)
        assert captions[0]["start"] == 0.0
        assert captions[0]["text"] == "we"
        assert captions[-1]["end"] == 10.0

    def test_never_exceeds_the_clip_duration(self):
        transcript = ClipService._clip_transcript(SEGMENTS, 100.0, 110.0)
        captions = ClipService._clip_captions(transcript, 100.0, 110.0)
        assert all(0.0 <= c["start"] <= c["end"] <= 10.0 for c in captions)

    def test_sorted_by_start(self):
        transcript = ClipService._clip_transcript(SEGMENTS, 100.0, 110.0)
        captions = ClipService._clip_captions(transcript, 100.0, 110.0)
        assert captions == sorted(captions, key=lambda c: c["start"])

    def test_falls_back_to_segment_text_without_word_timings(self):
        segments = [{"start": 10.0, "end": 12.0, "text": "no word timings here"}]
        captions = ClipService._clip_captions(segments, 10.0, 12.0)
        assert captions == [
            {"text": "no word timings here", "start": 0.0, "end": 2.0, "speaker": "Speaker"}
        ]

    def test_annotates_emoji_from_the_catalog(self):
        transcript = ClipService._clip_transcript(SEGMENTS, 100.0, 110.0)
        captions = ClipService._clip_captions(transcript, 100.0, 110.0)
        assert any(c.get("emoji") for c in captions)

    def test_ai_cues_override_the_static_map(self):
        transcript = ClipService._clip_transcript(SEGMENTS, 100.0, 110.0)
        captions = ClipService._clip_captions(
            transcript, 100.0, 110.0, [{"keyword": "money", "emoji": "gem"}]
        )
        money = next(c for c in captions if c["text"] == "money")
        assert money["emoji"] == "\U0001F48E"

    def test_ignores_ai_cues_outside_the_catalog(self):
        transcript = ClipService._clip_transcript(SEGMENTS, 100.0, 110.0)
        captions = ClipService._clip_captions(
            transcript, 100.0, 110.0, [{"keyword": "money", "emoji": "\U0001F984"}]
        )
        money = next(c for c in captions if c["text"] == "money")
        assert money.get("emoji") != "\U0001F984"

    def test_empty_transcript_yields_no_captions(self):
        assert ClipService._clip_captions([], 0.0, 10.0) == []
