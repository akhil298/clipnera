"""A full edit plans without the director: a cut filler never plays twice, and footage brought in twice is used once."""

from __future__ import annotations

from brain.full_edit import _distinct
from brain.solvers.speech_tighten import keep_ranges
from understanding.mud import MUD, Word


def _words(*spec: tuple[str, float, float, str | None]) -> list[Word]:
    return [Word(i=n, t0=t0, t1=t1, text=text, filler=filler, conf=0.99) for n, (text, t0, t1, filler) in enumerate(spec)]


def test_the_pads_around_a_cut_filler_stop_at_its_edges():
    # "like" is cut; the words either side stay. Neither kept piece may reach into "like".
    words = _words(*[(f"w{n}", n * 0.3, n * 0.3 + 0.25, None) for n in range(8)],
                   ("like", 2.37, 3.4, "like"), *[(f"v{n}", 3.42 + n * 0.3, 3.67 + n * 0.3, None) for n in range(8)])
    ranges = keep_ranges(words, 0.0, 6.0)
    assert len(ranges) == 2
    (_, end), (start, _) = ranges
    assert end <= 2.37 and start >= 3.4


def _mud(asset: str, text: str) -> MUD:
    words = [{"i": n, "t0": n * 0.4, "t1": n * 0.4 + 0.3, "text": w} for n, w in enumerate(text.split())]
    return MUD.model_validate({"asset_id": asset, "kind": "video", "duration": len(words) * 0.4, "words": words})


def test_the_same_footage_brought_in_twice_is_edited_once():
    talk = "we met when I was seven and you were sixty four and we have talked every week since then"
    videos = [("a", _mud("a", talk)), ("b", _mud("b", talk.replace("seven", "seven,"))), ("c", _mud("c", "a different video entirely about cooking pasta at home tonight"))]
    assert [asset for asset, _ in _distinct(videos)] == ["a", "c"]


def test_the_plan_outline_reads_part_by_part():
    from brain.outline import outline
    from editor.timeline import Timeline

    mud = MUD.model_validate({
        "asset_id": "a", "kind": "video", "duration": 60.0,
        "words": [{"i": 0, "t0": 0.0, "t1": 0.4, "text": "Hello"}, {"i": 1, "t0": 0.5, "t1": 0.9, "text": "there."},
                  {"i": 2, "t0": 40.0, "t1": 40.4, "text": "Second"}, {"i": 3, "t0": 40.5, "t1": 40.9, "text": "part."}],
        "utterances": [{"id": "u0", "w0": 0, "w1": 1, "t0": 0.0, "t1": 0.9, "text": "Hello there."},
                       {"id": "u1", "w0": 2, "w1": 3, "t0": 40.0, "t1": 40.9, "text": "Second part."}],
    })
    timeline = Timeline.model_validate({
        "assets": {"a": {"id": "a", "kind": "video", "key": "k", "frames": 1800}},
        "tracks": [
            {"id": "v1", "kind": "video", "items": [
                {"type": "clip", "id": "c1", "at": 0, "asset": "a", "src_in": 0, "src_out": 600},
                # 2 s left out, then a closer shot: the first part runs past 30 s, so it ends here.
                {"type": "clip", "id": "c2", "at": 600, "asset": "a", "src_in": 660, "src_out": 1020, "transform": {"scale": 1.2}},
                {"type": "clip", "id": "c3", "at": 960, "asset": "a", "src_in": 1170, "src_out": 1260, "speed": 0.5},
            ]},
            {"id": "t1", "kind": "text", "items": [{"type": "text", "id": "x", "at": 30, "text": "57 YEARS", "style": "title", "dur": 60}]},
            {"id": "s1", "kind": "audio", "items": [{"type": "sfx", "id": "s", "at": 30, "name": "pop", "dur": 10}]},
        ],
    })
    first, second = outline(timeline, {"a": mud})
    assert (first.start, first.end, first.said) == (0.0, 32.0, "“Hello there.”")
    assert first.actions == ["1 cut (2 s of pauses, fillers and retakes out)", "Closer shot at 0:20",
                             "“57 YEARS” on screen at 0:01", "pop sound at 0:01"]
    assert (second.start, second.said, second.actions) == (32.0, "“Second part.”", ["Slow motion (0.5×) at 0:32"])


def test_the_ai_finds_effects_with_the_operation_that_applies_them():
    from brain import effects

    counts = effects.counts()
    assert counts["sound"] > 200 and counts["graphic"] >= 16 and counts["look"] == 7 and counts["caption_style"] >= 20
    slow = effects.find("speed", "slow")[0]
    assert slow["id"] == "slow_motion" and "speed: 0.5" in slow["apply"]
    leak = effects.find("graphic", "light leak")[0]
    assert 'extra: {graphic: "light_leak"}' in leak["apply"] and leak["apply"].startswith("add_item {track: <id of a graphic track")
    assert effects.find("sound", "whoosh")[0]["apply"].startswith("add_item {track: <id of an audio track")
    assert effects.find("look", "warm")[0]["apply"] == 'set_project {look: "warm_film"}'


def test_the_ai_sees_graphics_and_flashes_on_its_stills():
    import numpy as np

    from brain import library
    from brain.frames import draw_layers

    grey = np.full((360, 640, 3), 100, np.uint8)
    flashed = draw_layers(grey, [("solid", "#FFFFFF", 0.0)])
    assert flashed.min() == 255
    leak = library.graphics()["light_leak"]
    drawn = draw_layers(grey, [("graphic", str(leak.video), 0.5)])
    # Half a second in, the light leak brightens the picture; at its very start it has barely begun.
    assert drawn.mean() > grey.mean() + 10
    assert abs(draw_layers(grey, [("graphic", str(leak.video), 0.0)]).mean() - grey.mean()) < abs(drawn.mean() - grey.mean())


def test_footage_with_its_own_subtitles_gets_no_captions_over_them():
    from types import SimpleNamespace

    from brain import full_edit
    from editor.timeline import Timeline

    mud = MUD.model_validate({
        "asset_id": "a", "kind": "video", "duration": 4.0,
        "words": [{"i": 0, "t0": 0.0, "t1": 0.5, "text": "Hello"}, {"i": 1, "t0": 0.6, "t1": 1.0, "text": "there."}],
        "utterances": [{"id": "u0", "w0": 0, "w1": 1, "t0": 0.0, "t1": 1.0, "text": "Hello there."}],
    })
    timeline = Timeline.model_validate({"assets": {"a": {"id": "a", "kind": "video", "key": "k", "frames": 120, "width": 1920, "height": 1080}}})
    ctx = SimpleNamespace(timeline=timeline, muds={"a": mud})
    kinds = lambda subtitled: [s.kind for s in full_edit.build(ctx, subtitled=subtitled)[1].steps]  # noqa: E731
    assert "captions" in kinds(frozenset())
    _, plan = full_edit.build(ctx, subtitled=frozenset({"a"}))
    assert "captions" not in [s.kind for s in plan.steps] and "own subtitles" in plan.summary
