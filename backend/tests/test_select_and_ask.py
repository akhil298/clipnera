"""Select & ask: a request about one selected stretch of the timeline."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from brain.route import digest
from brain.schema import AgentRequest, FramePoint, FrameRange
from brain.studio import PROMPT_CHARS, scoped
from editor.timeline import Timeline


def test_a_range_must_end_after_it_starts():
    assert FrameRange(start=10, end=20).end == 20
    with pytest.raises(ValidationError):
        FrameRange(start=20, end=20)
    with pytest.raises(ValidationError):
        FrameRange(start=-1, end=5)


def test_requests_without_a_range_are_unchanged():
    request = AgentRequest(prompt="Make it punchier")
    assert request.range is None
    assert scoped(request, 30) == "Make it punchier"


def test_the_prompt_names_the_range_for_the_router_and_director():
    request = AgentRequest(prompt="Make this faster", range=FrameRange(start=1260, end=2100))
    text = scoped(request, 30)
    assert text.startswith("Make this faster")
    assert "0:42" in text and "1:10" in text and "leave the rest as it is" in text


def test_a_long_prompt_still_fits_with_its_range():
    request = AgentRequest(prompt="x" * 2000, range=FrameRange(start=0, end=30))
    assert len(scoped(request, 30)) == PROMPT_CHARS


def test_the_studio_digest_shows_the_range():
    timeline = Timeline(fps=30, tracks=[{"id": "v1", "kind": "video", "items": []}])
    assert "Selected range" not in digest(timeline, [], 0)
    line = digest(timeline, [], 0, (1260, 2100)).splitlines()[-1]
    assert line.startswith("Selected range: 42.0s to 70.0s (frames 1260 to 2100)")


def test_rules_go_with_every_request():
    request = AgentRequest(prompt="Tighten it", rules=["Never cut the guest mid-sentence", "Captions: max 3 words"])
    text = scoped(request, 30)
    assert text.startswith("Tighten it")
    assert "- Never cut the guest mid-sentence" in text and "- Captions: max 3 words" in text


def test_rules_and_a_range_together_still_fit():
    request = AgentRequest(prompt="y" * 2000, range=FrameRange(start=0, end=30), rules=["r" * 200] * 20)
    text = scoped(request, 30)
    assert len(text) <= PROMPT_CHARS
    assert "of the timeline only" in text and text.startswith("y")


def test_rules_are_checked():
    with pytest.raises(ValidationError):
        AgentRequest(prompt="x", rules=[""])
    with pytest.raises(ValidationError):
        AgentRequest(prompt="x", rules=["r"] * 21)


def test_a_point_names_the_spot_and_the_frame():
    request = AgentRequest(prompt="Blur this", playhead=360, point=FramePoint(x=0.35, y=0.4))
    text = scoped(request, 30)
    assert "35% across and 40% down" in text and "0:12" in text


def test_points_stay_inside_the_frame():
    with pytest.raises(ValidationError):
        FramePoint(x=1.2, y=0.5)
