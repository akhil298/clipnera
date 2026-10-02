from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from editor.ops import Op, apply_ops
from editor.timeline import Timeline, TimelineError, check, to_frames

# Shared with frontend/lib/editor/timeline.test.mts, so both appliers agree.
FIXTURES = json.loads((Path(__file__).parents[1] / "editor" / "fixtures" / "timeline_ops.json").read_text())
BASE = Timeline.model_validate(FIXTURES["base"])
OPS = TypeAdapter(list[Op])


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda case: case["name"])
def test_shared_fixture(case: dict) -> None:
    ops = OPS.validate_python(case["ops"])
    expect = case["expect"]
    if "error" in expect:
        with pytest.raises(TimelineError) as caught:
            apply_ops(BASE, ops)
        assert (caught.value.code, caught.value.extra["op_index"]) == (expect["error"], expect["op_index"])
    else:
        assert apply_ops(BASE, ops) == Timeline.model_validate(expect["timeline"])


def test_apply_ops_leaves_the_input_alone() -> None:
    before = BASE.model_dump()
    apply_ops(BASE, OPS.validate_python([{"op": "remove_item", "item": "c1", "ripple": True}]))
    assert BASE.model_dump() == before


def test_the_base_fixture_is_a_valid_timeline() -> None:
    check(BASE)
    assert BASE.duration == 450


def test_frames_round_half_up_like_the_browser() -> None:
    assert [to_frames(v) for v in (0.5, 1.5, 2.5, 2.49)] == [1, 2, 3, 2]


def test_a_clip_slowed_down_lasts_longer() -> None:
    timeline = apply_ops(BASE, OPS.validate_python([
        {"op": "remove_item", "item": "c2"},
        {"op": "update_item", "item": "c1", "patch": {"speed": 0.5}},
    ]))
    assert timeline.find("c1")[1].frames == 600


def test_audio_only_assets_cannot_be_shown() -> None:
    with pytest.raises(TimelineError, match="audio only") as caught:
        apply_ops(BASE, OPS.validate_python([
            {"op": "add_asset", "asset": {"id": "vo", "kind": "audio", "key": "vo.mp3", "frames": 90}},
            {"op": "add_item", "track": "o1", "item": {"type": "clip", "id": "x", "asset": "vo", "at": 300, "src_in": 0, "src_out": 30}},
        ]))
    assert caught.value.extra["op_index"] == 1


def test_captions_must_follow_a_track_with_speech() -> None:
    with pytest.raises(TimelineError) as caught:
        apply_ops(BASE, OPS.validate_python([{"op": "set_captions", "follow": "t1"}]))
    assert caught.value.code == "UNKNOWN_TRACK"


def test_unknown_operations_are_refused_before_anything_runs() -> None:
    with pytest.raises(Exception):
        OPS.validate_python([{"op": "delete_everything"}])
