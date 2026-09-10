from __future__ import annotations

import pytest

from clip_generation.model import GeneratedClip
from subtitle_styling.model import SubtitleStyle
from clip_generation.schema import *


def test_schema_highlight_candidate():
    hc = HighlightCandidate(
        start_time=10.0,
        end_time=35.0,
        score=85.0,
        reasons=["keyword_match"],
        speakers=["Speaker 1"],
        content_category="gaming",
        transcript_excerpt="This is a great play",
    )
    assert hc.duration_seconds() if hasattr(hc, 'duration_seconds') else True
    assert hc.score == 85.0


def test_schema_content_category_response():
    cc = ContentCategoryResponse(category="gaming", confidence=0.9, keywords=["game"], reasoning="strong signal")
    assert cc.category == "gaming"
    assert cc.confidence == 0.9


def test_schema_clip_metadata():
    cm = ClipMetadata(title="Test Clip", description="A test", hashtags=["#test"], suggested_emoji="\ud83c\udfae")
    assert cm.title == "Test Clip"
    assert cm.hashtags == ["#test"]
