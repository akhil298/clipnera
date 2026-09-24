"""The teaser played before a clip, and how captions stay in sync around it.

The rendered file is the hook span followed by the clip span, so every word
must land at the same output position whether the editor, the ASS burner or
the SRT burner is placing it.
"""

from __future__ import annotations

import pytest

from clip_generation.hook import Hook, locate_hook, on_output_timeline
from clip_generation.service import ClipService

LINE = "So we started in a garage. Then we lost two million dollars in one afternoon. It changed everything."
WORDS = LINE.split()
SEGMENTS = [
    {
        "start": 100.0,
        "end": 100.0 + len(WORDS) * 0.5,
        "text": LINE,
        "speaker": "A",
        "words": [
            {"start": 100.0 + i * 0.5, "end": 100.0 + i * 0.5 + 0.45, "word": word}
            for i, word in enumerate(WORDS)
        ],
    },
]
CLIP_START, CLIP_END = 100.0, 100.0 + len(WORDS) * 0.5


class TestLocateHook:
    def test_matches_quote_to_word_timings(self):
        hook = locate_hook("we lost two million dollars in one afternoon", SEGMENTS, CLIP_START, CLIP_END)
        assert hook is not None
        assert (hook.start, hook.end) == (pytest.approx(103.5), pytest.approx(107.45))

    def test_ignores_case_and_punctuation(self):
        hook = locate_hook("We lost two million dollars, in one afternoon!", SEGMENTS, CLIP_START, CLIP_END)
        assert hook is not None and hook.start == pytest.approx(103.5)

    def test_rejects_the_opening_line(self):
        assert locate_hook("So we started in a garage", SEGMENTS, CLIP_START, CLIP_END) is None

    def test_rejects_unknown_or_empty_quote(self):
        assert locate_hook("we won the lottery", SEGMENTS, CLIP_START, CLIP_END) is None
        assert locate_hook("", SEGMENTS, CLIP_START, CLIP_END) is None

    def test_rejects_a_single_word(self):
        assert locate_hook("afternoon", SEGMENTS, CLIP_START, CLIP_END) is None


class TestOutputTimeline:
    def test_without_hook_is_unchanged(self):
        items = [{"start": 101.0, "end": 102.0}]
        assert on_output_timeline(items, 100.0, 110.0, None) == (100.0, items)

    def test_teaser_first_then_clip_shifted_by_hook(self):
        hook = Hook(105.0, 108.0)
        items = [
            {"start": 99.0, "end": 99.5, "text": "before"},
            {"start": 100.0, "end": 100.5, "text": "open"},
            {"start": 105.0, "end": 105.5, "text": "peak"},
        ]
        origin, placed = on_output_timeline(items, 100.0, 110.0, hook)
        assert [(i["text"], i["start"] - origin) for i in placed] == [
            ("peak", 0.0),
            ("open", 3.0),
            ("peak", 8.0),
        ]


class TestClipCaptionsWithHook:
    def test_editor_captions_open_on_the_teaser(self):
        hook = locate_hook("we lost two million dollars in one afternoon", SEGMENTS, CLIP_START, CLIP_END)
        captions = ClipService._clip_captions(SEGMENTS, CLIP_START, CLIP_END, hook=hook)

        teaser = captions[:8]
        assert [c["text"] for c in teaser][:2] == ["we", "lost"]
        assert teaser[0]["start"] == 0.0
        # The clip's own first word follows the teaser.
        first_body = captions[8]
        assert first_body["text"] == "So"
        assert first_body["start"] == round(hook.duration, 3)
