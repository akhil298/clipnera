"""The studio preview's overlay comes from the renderer's own compiled timeline."""

from __future__ import annotations

from brain.preview import caption_look, caption_styles, preview
from editor.timeline import Timeline
from understanding.mud import MUD


def _timeline(captions: bool = True) -> Timeline:
    return Timeline.model_validate({
        "fps": 30, "width": 1920, "height": 1080, "look": "warm_film",
        "assets": {"a1": {"id": "a1", "kind": "video", "key": "editor/u/p/a.mp4", "frames": 900, "has_audio": True}},
        "tracks": [
            {"id": "v1", "kind": "video", "items": [
                # 2–4 s of the footage, played at 2× from 1 s on the timeline.
                {"type": "clip", "id": "c1", "at": 30, "asset": "a1", "src_in": 60, "src_out": 120, "speed": 2},
            ]},
            {"id": "t1", "kind": "text", "items": [
                {"type": "text", "id": "x1", "at": 0, "text": "Hook", "style": "title", "dur": 30, "transform": {"y": 0.3}},
                {"type": "text", "id": "x2", "at": 60, "text": "Lower", "style": "studio", "dur": 30, "transform": {"y": 0.72}},
            ]},
            {"id": "a2", "kind": "audio", "items": [{"type": "sfx", "id": "s1", "at": 45, "name": "whoosh", "dur": 15}]},
        ],
        **({"captions": {"enabled": True, "style": "karaoke", "follow": "v1"}} if captions else {}),
    })


def _mud() -> MUD:
    return MUD.model_validate({
        "asset_id": "a1", "kind": "video", "duration": 30.0,
        "words": [
            {"i": 0, "t0": 1.0, "t1": 1.5, "text": "before"},
            {"i": 1, "t0": 2.0, "t1": 2.4, "text": "first"},
            {"i": 2, "t0": 3.0, "t1": 3.6, "text": "second"},
            {"i": 3, "t0": 4.5, "t1": 5.0, "text": "after"},
        ],
    })


def test_caption_words_follow_the_cut_and_the_speed():
    found = preview(_timeline(), {"a1": _mud()}, version=7)
    assert found.version == 7 and found.look == "warm_film" and found.caption_style == "karaoke"
    assert [(w.word, w.start, w.end) for w in found.words] == [("first", 1.0, 1.2), ("second", 1.5, 1.8)]


def test_titles_and_sounds_are_what_the_renderer_draws():
    found = preview(_timeline(), {"a1": _mud()}, version=1)
    assert [(t.kind, t.text, t.at) for t in found.texts] == [("hook", "Hook", 0.0), ("line", "Lower", 2.0)]
    assert [(s.name, s.at) for s in found.sounds] == [("whoosh", 1.5)]


def test_no_captions_when_they_are_off():
    found = preview(_timeline(captions=False), {"a1": _mud()}, version=1)
    assert found.words == [] and found.caption_look is None and found.caption_style is None


def test_the_caption_look_comes_from_the_template_catalogue():
    look = caption_look("karaoke")
    assert look.font_family == "Montserrat ExtraBold" and look.highlight_color.upper() == "#7CF25A"
    assert 0 < look.position_y < 1 and look.max_words_per_line >= 1
    # Unknown and legacy ids resolve the way the renderer resolves them.
    assert caption_look("no-such-style").name == caption_look("karaoke").name


def test_every_caption_style_can_be_listed_with_its_look():
    styles = caption_styles()
    assert len(styles) == 21 and styles[0].id == "karaoke"
    assert all(s.look.font_family and s.name for s in styles)


def test_the_looks_route_lists_every_render_look():
    import asyncio

    from brain.api import list_looks
    from edit_engine.looks import LOOKS

    response = asyncio.run(list_looks({"user_id": "u"}))
    assert [look.id for look in response.data] == list(LOOKS)
    assert response.data[-1].label == "Black & white"
