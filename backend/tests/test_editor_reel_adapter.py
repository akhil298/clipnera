from __future__ import annotations

import pytest

from edit_engine import compiler, story
from editor.reel_adapter import FPS, from_reel
from editor.timeline import ClipItem

SIZE = (1080, 1920)
SOURCES = [
    {"key": "u/e/talk.mp4", "kind": "video", "duration": 60.0, "width": 1920, "height": 1080, "has_audio": True, "proxy_key": "u/e/talk.proxy.mp4"},
    {"key": "u/e/run.mp4", "kind": "video", "duration": 8.0, "width": 1080, "height": 1920, "has_audio": False},
    {"key": "u/e/shoes.jpg", "kind": "image", "duration": 0.0, "width": 1200, "height": 1200},
]


def analysis_for(*takes: tuple[str, float]) -> dict:
    words = [{"src": 0, "start": round(start + i * 0.4, 3), "end": round(start + i * 0.4 + 0.3, 3), "word": w}
             for text, start in takes for i, w in enumerate(text.split())]
    sentences = story.sentences_from_words(words)
    return {
        "words": words, "sentences": sentences,
        "shots": [{"id": "v0", "src": 0, "start": 0.0, "end": 60.0, "face_x": 0.4, "faces": 1, "usable": True, "brightness": 120.0},
                  {"id": "v1", "src": 1, "start": 0.0, "end": 8.0, "face_x": None, "faces": 0, "usable": True, "brightness": 90.0}],
        "photos": [{"id": "p0", "src": 2, "description": "red running shoes"}],
        "dropped": [],
    }


def talking_reel() -> dict:
    analysis = analysis_for(("Running every day changed my whole life for real.", 0.0),
                            ("These shoes are the reason I kept going every morning.", 5.0))
    plan = {"mode": "none", "sentences": ["s0", "s1"], "hook": "Listen up", "music": {"track_id": "m12"},
            "broll": [{"sentence": "s0", "visual": "v1"}, {"sentence": "s1", "visual": "p0"}]}
    return compiler.compile_timeline(analysis, plan, size=SIZE, target_seconds=0, max_seconds=45)


class TestTalkingReel:
    def test_converts_to_a_valid_timeline_with_every_part(self) -> None:
        timeline = from_reel(talking_reel(), SOURCES, caption_style="lime_stack", language="en", size=SIZE)
        assert {t.id for t in timeline.tracks} == {"v1", "hook", "voice", "sfx", "music"}
        assert set(timeline.assets) == {"s0", "s1", "s2"}
        assert timeline.captions is not None and timeline.captions.follow == "voice"

    def test_picture_still_tiles_the_reel_without_gaps(self) -> None:
        picture = from_reel(talking_reel(), SOURCES, caption_style="karaoke", language="en", size=SIZE).track("v1").items
        assert picture[0].at == 0
        for first, second in zip(picture, picture[1:]):
            assert second.at == first.end

    def test_broll_keeps_its_source(self) -> None:
        reel = talking_reel()
        picture = from_reel(reel, SOURCES, caption_style="karaoke", language="en", size=SIZE).track("v1").items
        assert [clip.asset for clip in picture] == [f"s{p['src']}" for p in reel["picture"]]


def test_a_photo_is_a_clip_of_any_length() -> None:
    reel = {"duration": 3.0, "picture": [{"kind": "image", "src": 2, "at": 0.0, "dur": 3.0}],
            "voice": [], "texts": [], "sfx": [], "words": [], "music": None}
    clip = from_reel(reel, SOURCES, caption_style="karaoke", language="en", size=SIZE).track("v1").items[0]
    assert (clip.asset, clip.src_in, clip.src_out) == ("s2", 0, 90)

    def test_face_crop_and_zoom_become_the_clip_transform(self) -> None:
        reel = talking_reel()
        first = next(p for p in reel["picture"] if p["kind"] == "video" and p["src"] == 0)
        clip = from_reel(reel, SOURCES, caption_style="karaoke", language="en", size=SIZE).track("v1").items[0]
        assert isinstance(clip, ClipItem)
        assert (clip.transform.x, clip.transform.scale) == (first["crop_x"], first["zoom"])

    def test_music_runs_the_whole_reel_under_the_voice(self) -> None:
        reel = talking_reel()
        timeline = from_reel(reel, SOURCES, caption_style="karaoke", language="en", size=SIZE)
        music = timeline.track("music").items[0]
        assert (music.at, music.dur) == (0, round(reel["duration"] * FPS))
        assert music.duck and music.gain_db == compiler.MUSIC_UNDER_VOICE_DB


def test_a_montage_has_no_captions_and_no_voice_track() -> None:
    plan = {"mode": "none", "layout": "montage", "montage": ["v1", "p0", "v1"], "energy": "high"}
    reel = compiler.compile_timeline({"shots": analysis_for()["shots"], "photos": analysis_for()["photos"]}, plan,
                                     size=SIZE, target_seconds=6, max_seconds=45)
    timeline = from_reel(reel, SOURCES, caption_style="karaoke", language="en", size=SIZE)
    assert timeline.captions is None
    assert [t.id for t in timeline.tracks] == ["v1"]
    assert timeline.duration == pytest.approx(reel["duration"] * FPS, abs=1)


def test_a_card_becomes_text_over_a_gap_in_the_picture() -> None:
    analysis = analysis_for(("Cheap shoes hurt.", 0.0), ("Buy a proper pair.", 3.0))
    plan = {"mode": "spoken", "script_lines": [
        {"text": "Cheap shoes hurt.", "sentences": ["s0"]},
        {"text": "Here is why.", "sentences": []},
        {"text": "Buy a proper pair.", "sentences": ["s1"]}]}
    reel = compiler.compile_timeline(analysis, plan, size=SIZE, target_seconds=0, max_seconds=45)
    timeline = from_reel(reel, SOURCES, caption_style="karaoke", language="en", size=SIZE)
    card = timeline.track("cards").items[0]
    assert (card.text, card.style) == ("Here is why.", "card")
    assert all(not (clip.at < card.end and card.at < clip.end) for clip in timeline.track("v1").items)


def test_a_rounded_end_never_runs_past_the_source() -> None:
    reel = {"duration": 2.0, "picture": [{"kind": "video", "src": 1, "in": 7.0, "out": 8.0, "at": 0.0, "zoom": 1.0}],
            "voice": [], "texts": [], "sfx": [], "words": [], "music": None}
    sources = [SOURCES[0], {**SOURCES[1], "duration": 7.99}]
    clip = from_reel(reel, sources, caption_style="karaoke", language="en", size=SIZE).track("v1").items[0]
    assert clip.src_out == 240
