"""Motion code: a graphic the model writes is cleaned to an allowlist before the renderer sees it."""

from __future__ import annotations

import pytest

from reel_engine.motion_code import Rejected, clean, free_area


def test_scripts_handlers_and_outside_urls_never_reach_the_renderer():
    for html in ('<div><script>alert(1)</script></div>', '<img src="x" onerror="alert(1)">', '<iframe src="https://x.io"></iframe>',
                 '<svg><animate attributeName="x"/></svg>'):
        with pytest.raises(Rejected):
            clean(html, "")
    for css in ('.a{background:url(https://x.io/a.png)}', '@import "x.css";', '.a{background:url("javascript:alert(1)")}'):
        with pytest.raises(Rejected):
            clean('<div class="a"></div>', css)


def test_allowed_markup_survives_and_unknown_attributes_are_dropped():
    html, css = clean('<div class="mg" onclick="x()" data-x="1"><svg viewBox="0 0 10 10"><path d="M0 0L10 10" pathLength="1"/>'
                      '<rect fill="url(#g)"/></svg><b>50&lt;x</b></div>', ".mg{fill:url(#g)}")
    assert "onclick" not in html and "data-x" not in html
    assert 'class="mg"' in html and 'd="M0 0L10 10"' in html and 'fill="url(#g)"' in html and "50&lt;x" in html
    assert css == ".mg{fill:url(#g)}"


def test_the_free_area_names_the_bands_around_the_face():
    assert "nobody" in free_area([])
    text = free_area([(300, 200, 800, 900)])
    assert "y 920-1840 (full width)" in text and "never draw over it" in text and "y 60-" not in text
    # A caption line on screen then is kept clear too: the band below the face splits around it.
    text = free_area([(300, 200, 800, 900)], [(100, 1300, 980, 1420)])
    assert "y 920-1280" in text and "y 1440-1840" in text and "captions" in text


def test_a_designed_moment_is_timed_to_its_words_and_ends_at_the_shot_cut():
    from reel_engine import compile as comp
    from reel_engine.director import DDesign
    from reel_engine.plan import VideoItem, Word

    words = [Word(i=i, src=0, t0=i * 0.4, t1=i * 0.4 + 0.3, text=t) for i, t in enumerate("we passed on over 400 deals in six years".split())]
    items = [VideoItem(id="v0", src=0, t0=0, t1=2.0, out0=0, out1=2.0), VideoItem(id="v1", src=0, t0=2.0, t1=4.0, out0=2.0, out1=4.0)]

    class D:
        designs = [DDesign(w0=0, w1=8, why="a counter"), DDesign(w0=5, w1=6, why="too short"), *[DDesign(w0=0, w1=1, why="x")] * 5]

    out = comp.design_track(D, words, items)
    first = out[0]
    assert first.kind == "code" and first.start == 0 and first.end == 2.0  # held to the cut, not over the next shot
    assert first.data["words"][4] == {"text": "400", "at": 1.6} and first.data["line"].startswith("we passed")
    assert len(out) <= comp.MAX_DESIGNS


def test_a_design_that_scores_well_replaces_the_templates_on_its_words_and_a_weak_one_does_not(monkeypatch, tmp_path):
    import asyncio
    from pathlib import Path

    from reel_engine import layout, motion_code
    from reel_engine.motion_code import MotionCode
    from reel_engine.plan import EditPlan, GraphicItem

    plan = EditPlan(duration=10, graphics=[GraphicItem(id="h", kind="hook", start=0, end=2), GraphicItem(id="c", kind="count_up", start=3, end=5),
                                           GraphicItem(id="k", kind="keyword", start=7, end=8)])
    good = GraphicItem(id="d0", kind="code", start=3, end=5, data={"line": "400 deals", "words": []})
    weak = GraphicItem(id="d1", kind="code", start=7, end=8, data={"line": "passed", "words": []})

    async def ffmpeg(*args):  # the frame grab: writes its output file
        Path(args[-1]).write_bytes(b"jpg")

    async def make(line, *a, **k):
        return (MotionCode(html="<div></div>", css="", why="counter"), tmp_path / "x.mov", 8 if line == "400 deals" else 4, 2)

    monkeypatch.setattr(motion_code, "_ffmpeg", ffmpeg)
    monkeypatch.setattr(motion_code, "make", make)
    monkeypatch.setattr(layout, "look", lambda *a: ([], None))
    calls = asyncio.run(motion_code.design(plan, [good, weak], tmp_path / "picture.mp4", tmp_path))
    assert [g.id for g in plan.graphics] == ["h", "d0", "k"] and calls == 4
    assert plan.graphics[1].data["html"] == "<div></div>"


def test_where_a_graphic_paints_is_measured_and_covering_a_caption_is_a_problem(tmp_path):
    import cv2
    import numpy as np

    from reel_engine.motion_code import clashes, drawn_box

    layer = np.zeros((1920, 1080, 4), np.uint8)
    layer[1200:1400, 100:900] = (255, 255, 255, 255)
    cv2.imwrite(str(tmp_path / "a.png"), layer)
    cv2.imwrite(str(tmp_path / "empty.png"), np.zeros((1920, 1080, 4), np.uint8))
    assert drawn_box([tmp_path / "a.png", tmp_path / "empty.png"]) == (100, 1200, 899, 1399)
    assert drawn_box([tmp_path / "empty.png"]) is None
    box = (100, 1200, 899, 1399)
    hit = clashes(box, [("captions", (120, 1300, 960, 1420)), ("speaker's face", (300, 200, 800, 900))])
    assert len(hit) == 1 and "covers the captions" in hit[0]


def test_the_cta_and_captions_on_screen_are_kept_clear_but_full_frame_layers_are_not():
    from reel_engine.motion_code import on_screen
    from reel_engine.plan import CaptionLine, EditPlan, GraphicItem

    g = GraphicItem(id="d0", kind="code", start=10, end=12)
    plan = EditPlan(duration=14, graphics=[g, GraphicItem(id="c", kind="cta", start=11, end=13, box=[40, 1300, 600, 200]),
                                           GraphicItem(id="w", kind="wash", start=10, end=11, box=[0, 0, 1080, 1920]),
                                           GraphicItem(id="k", kind="keyword", start=10, end=12, box=[0, 0, 300, 100])],
                    captions=[CaptionLine(id="l", start=11.5, end=12.5, lead="a", keyword="b", box=[100, 1500, 800, 120])])
    names = [n for n, _ in on_screen(plan, g)]
    assert names == ["captions", "call-to-action card"]
