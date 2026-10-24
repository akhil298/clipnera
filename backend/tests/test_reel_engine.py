"""The reel engine's decisions that must hold for every reel: audio path, speech tightening, speeds, spacing,
captions, placement, the asset loop and the schemas the models answer in."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import numpy as np
import pytest

from clients.ai.openai import _strict_compatible
from reel_engine import compile as comp
from reel_engine.assets import AssetRecord, LocalAssetStore, Scout
from reel_engine.director import DBeat, DClip, DHook, DirectorPlan, DSection
from reel_engine.jobs import summary
from reel_engine.layout import free_top
from reel_engine.listen import classify, lyrics_score
from reel_engine.plan import AudioReport, EditPlan, GraphicItem, Shot, Word
from reel_engine.review import Verdict
from reel_engine.verify import Verdicts


def words_of(text: str, start: float = 0.0, gap: float = 0.05, src: int = 0) -> list[Word]:
    out, t = [], start
    for i, token in enumerate(text.split()):
        out.append(Word(i=i, src=src, t0=round(t, 3), t1=round(t + 0.3, 3), text=token))
        t += 0.3 + gap
    return out


def clip(**kw) -> DClip:
    base = dict(src=0, start=-1, end=-1, w0=-1, w1=-1, role="body", section=-1, zoom="in", money=False, sound="none", what="")
    return DClip(**{**base, **kw})


def beat(**kw) -> DBeat:
    base = dict(kind="two", w0=-1, w1=-1, src=-1, at=-1, until=-1, lead="", text="", items=[], number="", prefix="", suffix="",
                mark="none", trend="none", icon="", why="")
    return DBeat(**{**base, **kw})


def director(**kw) -> DirectorPlan:
    base = dict(audio_view="voice", recipe="creator_advice", target_seconds=30, title_lead="", title_text="", hook_text="", cta="",
                caption_mode="every_word", music="bed", type_kit="amber_block", mood="upbeat", sections=[], hooks=[], story=[], beats=[],
                inserts=[], scenes=[], keywords=[], burned_captions=False,
                drop_word=-1, spelling=[], style="podcast", effects=[], notes="", text_style=text_style())
    return DirectorPlan(**{**base, **kw})


def text_style(**kw):
    from reel_engine.director import DTextStyle

    base = dict(lead_font="Inter", lead_weight=700, lead_case="none", key_font="Unbounded", key_weight=800, key_case="uppercase",
                title_font="Unbounded", title_weight=900, title_case="uppercase", treatment="glow", lead_treatment="stroke",
                accent="#ff7a1a", alt="#ffffff", ink="#111111", why="warm glowing keywords")
    return DTextStyle(**{**base, **kw})


# ------------------------------------------------------------------ listen

def test_audio_kind_needs_speech_and_reads_music_under_it():
    assert classify(0.6, 0.0, -18, -40)[0] == "voice"
    assert classify(0.6, 0.0, -18, -20)[0] == "voice_song"
    assert classify(0.03, 0.0, -50, -20)[0] == "song"
    assert classify(0.0, 0.0, -80, -80)[0] == "silent"
    assert classify(0.7, 0.6, -18, -20)[0] == "song"  # lyrics: repeated lines, even with plenty of "speech"


def test_lyrics_score_spots_repeated_lines():
    chorus = "when you gonna give it up to me " * 6
    assert lyrics_score(words_of(chorus)) > 0.5
    assert lyrics_score(words_of("today we bake a potato then caramelise onions and sear a thick steak in butter")) == 0.0


# ------------------------------------------------------------------ compile: video

def test_talking_clips_drop_fillers_and_pauses_but_never_speed_up():
    words = words_of("so today um we make the best steak ever")
    words[2].filler = True
    words[5].t0, words[5].t1 = 5.0, 5.3  # a long pause before "the"
    for k in range(6, len(words)):
        words[k].t0, words[k].t1 = 5.35 + (k - 6) * 0.35, 5.65 + (k - 6) * 0.35
    d = director(story=[clip(w0=0, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 20.0})
    assert len(items) == 3  # split at the filler and at the pause
    assert all(i.speed == 1.0 and i.keeps_voice for i in items)
    assert items[0].t1 < words[2].t0 + 0.1 and items[1].t0 > words[2].t1 - 0.1
    assert items[1].zoom != items[2].zoom  # framing changes cover each jump cut


def test_picture_clips_get_clamped_speeds_and_money_shots_slow_down():
    d = director(audio_view="silent", recipe="recipe_process", story=[
        clip(start=0, end=12, role="step", section=0),
        clip(start=20, end=21.2, money=True),
        clip(start=30, end=30.3, role="montage", what="Eggs"),
    ], sections=[DSection(lead="Beat the", text="eggs", short="Eggs", icon="egg")])
    brief, _ = comp.brief_of(d, AudioReport(kind="silent"), 0)
    items = comp.video_track(d, brief, [], [], {0: 60.0})
    assert brief.path == "visual" and brief.music == "score" and brief.caption_mode == "none"
    assert 1.0 <= items[0].speed <= comp.MAX_SPEED
    assert items[1].speed < 1.0
    assert abs((items[2].out1 - items[2].out0) - comp.MONTAGE_SECONDS) < 0.04
    assert items[0].out0 == 0 and all(a.out1 == b.out0 for a, b in zip(items, items[1:]))


def test_a_song_measured_by_listen_is_not_edited_as_a_voice():
    d = director(audio_view="voice")
    brief, note = comp.brief_of(d, AudioReport(kind="song", lyrics=True), 0)
    assert brief.path == "visual" and note


# ------------------------------------------------------------------ compile: graphics and captions

def test_one_story_graphic_at_a_time():
    graphics = [GraphicItem(id="a", kind="two", start=1.0, end=3.0), GraphicItem(id="b", kind="tag", start=1.5, end=2.2),
                GraphicItem(id="c", kind="tag", start=2.0, end=5.0), GraphicItem(id="w", kind="wash", start=1.0, end=1.3)]
    kept = comp._space(graphics)
    story = sorted((g for g in kept if g.kind != "wash"), key=lambda g: g.start)
    assert len(story) == 2 and all(a.end <= b.start for a, b in zip(story, story[1:]))
    assert any(g.kind == "wash" for g in kept)


def test_beats_follow_their_words_and_drop_when_cut():
    words = words_of("ninety percent of traders never see a payout")
    d = director(story=[clip(w0=0, w1=4)], beats=[
        beat(kind="count_up", w0=0, w1=1, number="90", suffix="%", text="never paid"),
        beat(kind="keyword", w0=7, w1=8, text="payout"),  # those words were cut
    ])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 10.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    kinds = [g.kind for g in graphics]
    assert "count_up" in kinds and "keyword" not in kinds


def test_captions_stay_quiet_under_full_cards_and_take_the_tag_icon():
    words = words_of("add the ghee then the potato fry and it tastes amazing")
    d = director(story=[clip(w0=0, w1=len(words) - 1)], keywords=[2, 5], drop_word=10,
                 beats=[beat(kind="tag", w0=2, w1=2, text="Ghee", icon="butter"),
                        beat(kind="statement", w0=6, w1=7, text="Potato fry")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 20.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    captions, graphics = comp.captions_track(d, brief, words, items, graphics)
    cards = [(g.start, g.end) for g in graphics if g.kind == "statement"]
    assert captions and all(not (a < c.end and c.start < b) for c in captions for a, b in cards)
    assert not any(g.kind == "tag" for g in graphics)
    assert any(c.icon_query == "butter" for c in captions)
    assert any(c.payoff for c in captions)


def test_keyword_mode_shows_only_turning_points():
    words = words_of("it is not the market it is because of your behavior")
    d = director(caption_mode="keyword", story=[clip(w0=0, w1=len(words) - 1)], keywords=[10])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 20.0})
    captions, _ = comp.captions_track(d, brief, words, items, [])
    assert captions and all("behavior" in f"{c.lead} {c.keyword}" for c in captions)


def test_every_word_captions_keep_running_under_side_cards():
    words = words_of("there are three things every student must know before choosing a course")
    d = director(story=[clip(w0=0, w1=len(words) - 1)], beats=[beat(kind="list", w0=0, w1=len(words) - 1, text="Three things")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 20.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    captions, _ = comp.captions_track(d, brief, words, items, graphics)
    shown = " ".join(w["text"] for c in captions for w in c.words)
    assert "student" in shown and "course" in shown


def test_faces_that_never_move_are_not_followed():
    from reel_engine.plan import Box
    from reel_engine.watch import _still

    slide = np.full((144, 256, 3), 90, np.uint8)
    live = slide.copy()
    live[10:40, 200:240] = np.random.default_rng(1).integers(0, 255, (30, 40, 3), dtype=np.uint8)
    assert _still(Box(x=0.3, y=0.4, w=0.2, h=0.3), live, slide)
    assert not _still(Box(x=200 / 256, y=10 / 144, w=40 / 256, h=30 / 144), live, slide)


# ------------------------------------------------------------------ layout

def test_placement_avoids_faces_and_busy_detail():
    detail = np.zeros((170, 96), np.float32)
    detail[110:170, :] = 1.0  # food across the bottom third
    face = (300, 200, 780, 900)
    top = free_top([80, 0, 920, 230], [face], detail, 1300)
    assert top >= 900 and top + 230 <= 110 * 1920 / 170 + 20


# ------------------------------------------------------------------ the asset loop

def test_scout_makes_a_missing_sound_once_then_reuses_it(tmp_path: Path):
    store = LocalAssetStore(tmp_path / "store")

    async def run() -> tuple:
        first = Scout(store, "u1", tmp_path)
        made = await first.sound("sizzle")
        second = Scout(store, "u2", tmp_path)
        again = await second.sound("sizzle")
        await second.finish()
        return made, again, first.made, second.made

    made, again, first_made, second_made = asyncio.run(run())
    assert made and made.made and len(first_made) == 1
    assert again and again.id == made.id and not second_made
    assert (asyncio.run(store.search("sfx", {"sizzle"}, "anyone")))[0].uses == 1


def test_private_assets_stay_with_their_owner(tmp_path: Path):
    store = LocalAssetStore(tmp_path)
    file = tmp_path / "x.wav"
    file.write_bytes(b"0" * 128)
    asyncio.run(store.add(AssetRecord(kind="score", scope="user", owner="alice", words=["score"]), file))
    assert asyncio.run(store.search("score", {"score"}, "alice"))
    assert not asyncio.run(store.search("score", {"score"}, "bob"))


def test_scout_finds_kit_icons_and_known_sounds(tmp_path: Path):
    scout = Scout(LocalAssetStore(tmp_path), "u", tmp_path)
    assert asyncio.run(scout.sound("whoosh"))
    bed = scout.bed("upbeat")
    assert bed and Path(bed.path).exists()


# ------------------------------------------------------------------ contracts

@pytest.mark.parametrize("schema", [DirectorPlan, Verdicts, Verdict])
def test_model_replies_use_strict_schemas(schema):
    assert _strict_compatible(schema.model_json_schema())


def test_summary_reads_progress_before_a_plan_exists():
    queued = summary({"progress": [{"stage": "direct", "note": "planning", "at": 3.0}]})
    assert queued["stage"] == "direct" and queued["shots"] == 0 and queued["scores"] == []
    plan = EditPlan(shots=[Shot(id="s0", src=0, t0=0, t1=1)])
    done = summary({"plan": plan.model_dump(), "progress": [{"stage": "done", "note": "", "at": 9.0}]})
    assert done["stage"] == "done" and done["overall"] == 0.0


def test_hook_option_goes_first():
    words = words_of("hello there this is the best part")
    d = director(story=[clip(w0=0, w1=2)], hooks=[DHook(clip=clip(w0=4, w1=6), word="BEST", why="payoff")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 10.0})
    assert items[0].role == "hook" and items[0].t0 >= words[4].t0 - 0.1


def test_the_hook_line_is_not_said_twice():
    words = words_of("one two three four five six seven eight nine ten")
    d = director(story=[clip(w0=0, w1=9)], hooks=[DHook(clip=clip(w0=3, w1=5), word="FOUR", why="mid")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 10.0})
    said = sorted(w.i for w in words for i in items if i.t0 - 0.01 <= w.t0 and w.t1 <= i.t1 + 0.01)
    assert said == list(range(10))
    assert items[0].role == "hook" and items[0].t0 >= words[3].t0 - 0.1


def test_footage_with_its_own_text_is_shown_whole_not_cropped(tmp_path):
    from reel_engine.plan import Source, VideoItem
    from reel_engine.render import segment_cmd

    src = Source(index=0, name="a", path="a.mp4", kind="video", duration=60, width=1920, height=1080, fps=30)
    item = VideoItem(id="v0", src=0, t0=1, t1=4, out0=0, out1=3, zoom="punch", role="body")
    track = [[2.0, 0.2, 0.4, 0.1, 0.2, 0.0]]
    cropped = segment_cmd(src, item, track, "", 1.0, tmp_path / "g.cube", False, False, tmp_path / "o.mp4")
    fitted = segment_cmd(src, item, track, "", 1.0, tmp_path / "g.cube", False, False, tmp_path / "o.mp4", fit=True)
    vf = lambda cmd: cmd[cmd.index("-vf") + 1]  # noqa: E731
    assert "crop=iw*" in vf(cropped) and "crop=iw*" not in vf(fitted)
    assert "overlay=0:(H-h)/2" in vf(fitted) and "z='1.0'" in vf(fitted)


def test_on_a_fitted_reel_a_statement_moves_off_the_picture_strip():
    from reel_engine.layout import band_box

    strip = (0, 656, 1080, 1264)
    top, h = band_box([86, 384, 908, 1152], strip)[1:4:2]
    assert top + h <= strip[1] or top >= strip[3]


def test_the_window_frames_out_a_subtitle_band():
    from reel_engine.plan import Source, VideoItem
    from reel_engine.render import framing

    src = Source(index=0, name="a", path="a.mp4", kind="video", duration=60, width=1920, height=1080, fps=30)
    item = VideoItem(id="v0", src=0, t0=1, t1=4, out0=0, out1=3, zoom="in", role="body")
    track = [[t, 0.5, 0.3, 0.12, 0.25, 0.0] for t in (1.0, 2.0, 3.0)]
    crop, _ = framing(src, item, track, inside=[0.09, 1.0])
    height, top = (float(v) for v in re.findall(r"ih\*([0-9.]+)", crop))
    assert top >= 0.09 - 1e-4 and top + height <= 1.0 + 1e-4


def test_an_object_keeps_off_an_effects_card(monkeypatch):
    from reel_engine import layout
    from reel_engine.plan import GraphicItem

    monkeypatch.setattr(layout, "look", lambda video, a, b: ([], np.zeros((layout.DETAIL_H, layout.DETAIL_W), np.float32)))
    card = GraphicItem(id="e0f", kind="effect", start=0, end=3, box=[0, 0, 1080, 1920], data={"panel": [130, 1080, 820, 300]})
    obj = GraphicItem(id="o1", kind="object", start=1, end=2)
    layout.place([card, obj], [], "unused.mp4")
    x, y, w, h = obj.box
    assert y + h <= 1080 or y >= 1380


def test_a_still_photo_gives_its_frame(tmp_path):
    import cv2
    import numpy as np

    from reel_engine.media import frame

    path = tmp_path / "photo.jpg"
    cv2.imwrite(str(path), np.full((100, 160, 3), 200, np.uint8))
    assert frame(path, 0.0, 80) is not None


def test_chapters_open_with_a_wash_and_a_chaptered_reel_opens_on_its_title():
    d = director(audio_view="silent", recipe="recipe_process", title_lead="Three ways to", title_text="breakfast",
                 hooks=[DHook(clip=clip(start=50, end=52, money=True), word="BRIGHT", why="hero")],
                 sections=[DSection(lead="Make", text="eggs", short="Eggs", icon="egg"),
                           DSection(lead="Build", text="toast", short="Toast", icon="bread")],
                 story=[clip(start=0, end=6, role="step", section=0), clip(start=10, end=16, role="step", section=1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="silent"), 0)
    items = comp.video_track(d, brief, [], [], {0: 60.0})
    graphics = comp.graphics_track(d, brief, [], items, [])
    kinds = [g.kind for g in graphics]
    assert kinds.count("wash") == 2 and kinds.count("chapter") == 2
    opening = min(graphics, key=lambda g: g.start)
    assert opening.kind == "two" and opening.data["text"] == "breakfast" and opening.start < 0.5


def test_a_talking_reel_keeps_the_speaker_on_screen():
    cards = [GraphicItem(id=f"c{k}", kind="statement", start=k * 3.0, end=k * 3.0 + 2, place="card") for k in range(6)]
    kept = comp._few_cards(cards + [GraphicItem(id="w", kind="wash", start=0, end=0.3, place="card")], total=20.0)
    assert sum(1 for g in kept if g.kind == "statement") == 2 and any(g.kind == "wash" for g in kept)


def test_captions_never_repeat_a_word_graphic_and_skip_weak_keywords():
    words = words_of("but we have been working together really well up here")
    d = director(story=[clip(w0=0, w1=len(words) - 1)], beats=[beat(kind="two", w0=4, w1=5, lead="working", text="together")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 20.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    captions, _ = comp.captions_track(d, brief, words, items, graphics)
    two = next(g for g in graphics if g.kind == "two")
    under = [w["text"].lower() for c in captions if two.start < c.end and c.start < two.end for w in c.words]
    assert "working" not in under and "together" not in under
    assert all(c.keyword.lower() not in comp.WEAK for c in captions)


def test_music_is_picked_by_mood_and_lands_a_drop_on_the_reveal():
    from reel_engine import tracks

    track = tracks.Track(key="t", path=Path("t.mp3"), title="T", mood="upbeat", bpm=120, seconds=90, energy=0.6,
                         downbeats=tuple(i * 2.0 for i in range(40)), drops=((30.0, 1.0), (61.0, 0.5)), licence="x", source="mixkit")
    start = tracks.offset(track, reveal=6.0, seconds=25)
    assert start in track.downbeats and abs((30.0 - start) - 6.0) <= tracks.DROP_TOLERANCE
    assert tracks.offset(track, reveal=None, seconds=25) == 0.0
    assert abs(track.beat - 0.5) < 1e-9


def test_photo_cards_take_the_place_of_story_graphics():
    from reel_engine.pipeline import add_photo_cards
    from reel_engine.plan import AssetRef, CaptionLine, InsertItem

    plan = EditPlan(graphics=[GraphicItem(id="g0", kind="two", start=2, end=4), GraphicItem(id="g1", kind="chapter", start=2, end=3)],
                    captions=[CaptionLine(id="c0", start=2.5, end=3.5, lead="a", keyword="b")],
                    inserts=[InsertItem(id="i0", kind="photo", start=2, end=4, style="card",
                                        asset=AssetRef(id="a", kind="photo", path="p.jpg", licence="cc0", source="openverse"))])
    add_photo_cards(plan)
    kinds = [g.kind for g in plan.graphics]
    assert "photocard" in kinds and "two" not in kinds and "chapter" in kinds and not plan.captions and not plan.inserts


def test_a_content_filter_flag_retries_with_fewer_frames(monkeypatch):
    import httpx

    import clients.ai as ai_clients
    from reel_engine import ai

    calls = []

    class Client:
        def image_message(self, text, frames):
            return {"role": "user", "content": text, "frames": len(frames)}

        async def chat_json(self, messages, schema, **kwargs):
            frames = messages[-1].get("frames", 0)
            calls.append(frames)
            if frames >= 2:
                request = httpx.Request("POST", "https://x")
                raise httpx.HTTPStatusError("400", request=request, response=httpx.Response(
                    400, request=request, text='{"error": {"code": "content_policy_violation"}}'))
            return schema(picks=[])

    monkeypatch.setattr(ai_clients, "get_text_client", lambda **kw: Client())
    from reel_engine.inserts import Picks
    result = asyncio.run(ai.vision_json("s", "t", [b"a", b"b", b"c", b"d"], Picks, 100, step="reel_photos"))
    assert result.picks == [] and calls == [4, 2, 2, 0]


def test_each_reel_step_runs_on_its_model_and_a_setting_overrides_it(monkeypatch):
    import clients.ai as ai_clients
    from core.config import get_settings
    from reel_engine import ai

    monkeypatch.setattr(ai_clients, "get_text_client", lambda choice: choice)
    director = ai.client("reel_director")
    assert (director.provider, director.model, director.effort) == ("openai", "gpt-6.1-sol-1", "medium")
    assert (ai.client("reel_proof").model, ai.client("reel_proof").effort) == ("gpt-4.1-mini-1", None)
    monkeypatch.setattr(get_settings(), "REEL_STEP_MODELS", {"reel_director": "openai:gpt-6-astra-1:high"})
    assert (ai.client("reel_director").model, ai.client("reel_director").effort) == ("gpt-6-astra-1", "high")


# ------------------------------------------------------------------ checklists

def test_checklist_items_land_as_spoken_and_captions_do_not_repeat_them():
    words = words_of("you can be a poor student or an average student or a topper and still pass", gap=0.3)
    d = director(story=[clip(w0=0, w1=len(words) - 1)],
                 beats=[beat(kind="list", w0=0, w1=len(words) - 1, items=["Poor student", "Average student", "Topper"], mark="check")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 30.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    panel = next(g for g in graphics if g.kind == "list")
    said = {w.text: comp.to_output(items, 0, w.t0) for w in words}
    landed = [panel.start + s for s in panel.data["steps"]]
    assert abs(landed[0] - said["poor"]) < 0.05 and abs(landed[1] - said["average"]) < 0.05 and abs(landed[2] - said["topper"]) < 0.05
    assert panel.start <= said["poor"] and said["poor"] - panel.start < 0.4
    captions, _ = comp.captions_track(d, brief, words, items, graphics)
    under = [w["text"] for c in captions if panel.start < c.end and c.start < panel.end for w in c.words]
    assert "topper" not in under and "poor" not in under


def test_checklist_steps_fill_unheard_items_between_neighbours():
    assert comp._steps([1.0, None, 2.0], 0.8, 4.0) == [0.2, 0.7, 1.2]


def test_checklist_panel_fits_its_rows():
    from reel_engine.layout import default_box

    two, five = default_box("list", {"items": ["a", "b"]}), default_box("list", {"items": list("abcde")})
    assert two[3] < five[3] <= 760 and two[3] < 500


def test_each_checklist_item_gets_a_quiet_click():
    from reel_engine import sound

    plan = EditPlan(duration=10.0, graphics=[GraphicItem(id="g", kind="list", start=2.0, end=5.0, data={"steps": [0.2, 1.0, 1.8]})])

    class S:
        async def sound(self, name):
            from reel_engine.plan import AssetRef
            return AssetRef(id=name, kind="sfx", path=f"/{name}.wav", licence="", source="test")

    out = asyncio.run(sound.effects(plan, S()))
    clicks = [at for at, ref, gain in out if ref.id == sound.STEP_SOUND]
    assert clicks == [2.2, 3.0, 3.8] and all(gain < sound.EFFECT_GAIN for _, ref, gain in out if ref.id == sound.STEP_SOUND)


# ------------------------------------------------------------------ effects

def fx(**kw):
    from reel_engine.effects import DEffect

    return DEffect(**{**dict(name="orbit", w0=2, w1=8, texts=[], choice="", target="", why=""), **kw})


def test_effect_picks_are_held_to_the_catalog():
    from reel_engine import effects

    words = words_of("so many things design code marketing sales hiring and then everyone was talking about it online today "
                     "and i felt like the king of the whole world for one single day", gap=0.4)
    d = director(story=[clip(w0=0, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 60.0})
    picks = [fx(name="orbit", w0=3, w1=7, texts=["Design", "Code", "Marketing and growth hacking", "Sales"]),
             fx(name="orbit", w0=8, w1=9, texts=["a", "b", "c"]),                                  # a second orbit: over the limit
             fx(name="headline_wall", w0=11, w1=15, texts=["Only one headline"]),                    # too few texts
             fx(name="nonsense", w0=12, w1=13),                                                      # not in the catalog
             fx(name="doodle", w0=27, w1=29, choice="crown", target="moon")]                         # bad target -> first allowed
    made = effects.compile_effects(picks, words, items)
    names = [g.data["effect"] for g in made]
    assert names.count("orbit") == 2 and {g.data["part"] for g in made if g.data["effect"] == "orbit"} == {"back", "front"}
    orbit = next(g for g in made if g.data["effect"] == "orbit")
    assert orbit.data["texts"][2] == "Marketing and" and next(g for g in made if g.data["part"] == "back").behind
    assert "headline_wall" not in names and "nonsense" not in names
    doodle = next(g for g in made if g.data["effect"] == "doodle")
    assert doodle.data["target"] == "face_top" and doodle.start - orbit.end >= effects.catalog()["min_gap"]


def test_zoom_through_snaps_to_a_cut_or_is_dropped():
    from reel_engine import effects

    words = words_of("first idea here and now a whole new idea starts right here")
    d = director(story=[clip(w0=0, w1=4), clip(w0=6, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 60.0})
    cut = items[1].out0
    made = effects.compile_effects([fx(name="zoom_through", w0=6, w1=6)], words, items)
    assert len(made) == 1 and abs((made[0].start + made[0].end) / 2 - cut) < 0.01
    # A take short enough to stay one shot (a longer one is reframed every ~2 s, which is a cut to zoom through).
    single = comp.video_track(director(story=[clip(w0=0, w1=6)]), brief, words, [], {0: 60.0})
    assert len(single) == 1 and effects.compile_effects([fx(name="zoom_through", w0=3, w1=3)], words, single) == []


def test_story_graphics_and_captions_make_way_for_an_effect():
    from reel_engine import effects

    words = words_of("this was all over the news and every paper had it on the front page that week", gap=0.3)
    d = director(story=[clip(w0=0, w1=len(words) - 1)], beats=[beat(kind="two", w0=5, w1=6, lead="every", text="paper")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 60.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    wall = effects.compile_effects([fx(name="headline_wall", w0=4, w1=9, texts=["All over the news", "Every paper had it", "Front page"])],
                                   words, items)
    graphics = effects.clear_under(graphics, wall) + wall
    assert not any(g.kind == "two" for g in graphics)
    captions, _ = comp.captions_track(d, brief, words, items, graphics)
    assert all(not (wall[0].start < c.end and c.start < wall[0].end) for c in captions)


def test_director_prompt_lists_every_catalog_effect():
    from reel_engine import effects

    text = effects.prompt()
    assert all(name in text for name in effects.catalog()["effects"])
    assert "STYLE allows" in text


def test_picture_effects_build_a_filter_and_need_a_matte_where_said():
    from reel_engine import effects

    for name in ("pullback", "zoom_through", "glass_type", "phone_mockup"):
        g = effects.make_items("x", name, 1.0, 2.5, ["Values never change"] if name == "glass_type" else [])[0]
        g.data["face"], g.data["panel"] = [400, 300, 700, 650], effects.panel_box([400, 300, 700, 650])
        assert "[out]" in effects.picture_filter(g, 1.5, False)
    vertigo = effects.make_items("v", "vertigo", 1.0, 2.5, [])[0]
    vertigo.data["face"] = [400, 300, 700, 650]
    assert effects.picture_filter(vertigo, 1.5, False) is None and "alphamerge" in effects.picture_filter(vertigo, 1.5, True)


def test_caption_lines_follow_phrases():
    words = words_of("so you have to balance kar lo the whole thing. then we move on to the next step", gap=0.05)
    words[10].t0 += 0.5  # a pause before "then"
    for w in words[11:]:
        w.t0 += 0.5
        w.t1 += 0.5
    kept = [(w, w.t0, w.t1) for w in words]
    lines = [" ".join(e[0].text for e in line) for line in comp.phrase_lines(kept)]
    assert all(not line.split()[-1] in comp.BINDING for line in lines[:-1]), lines
    assert any(line.endswith("thing.") for line in lines) and all(2 <= len(line.split()) <= 6 for line in lines), lines
    assert "kar | lo" not in " | ".join(lines)


# ------------------------------------------------------------------ framing

def _src(w=1920, h=1080):
    from reel_engine.plan import Source

    return Source(index=0, name="a.mp4", path="a.mp4", kind="video", duration=60, width=w, height=h)


def _item(t0=0.0, t1=3.0):
    from reel_engine.plan import VideoItem

    return VideoItem(id="v", src=0, t0=t0, t1=t1, out0=0, out1=t1 - t0, speed=1.0, zoom="hold")


def test_framing_follows_the_person_talking_not_the_biggest_face():
    from reel_engine import render

    rows = []
    for k in range(12):
        t = k * 0.25
        rows.append([t, 0.3, 0.4, 0.12, 0.2, 0.002])   # big face, listening
        rows.append([t, 0.75, 0.4, 0.08, 0.14, 0.04])  # smaller face, talking
    found = render.people(rows)
    chosen, pair = render.pick_people(found, 3.0)
    assert pair is None and abs(chosen["x"] - 0.75) < 0.05
    crop, _ = render.framing(_src(), _item(), rows)
    left = float(crop.split("'(")[1].split(")*iw'")[0].split(",")[-1].rstrip(")"))
    assert left > 0.4  # the window sits over the right-hand speaker


def test_two_people_trading_lines_get_a_split_screen():
    from reel_engine import render

    rows = [[k * 0.25, x, 0.4, 0.09, 0.15, talk] for k in range(12) for x, talk in ((0.3, 0.03), (0.72, 0.025))]
    crop, _ = render.framing(_src(), _item(), rows)
    assert "vstack" in crop and crop.count("crop=") == 2


def test_nobody_on_screen_frames_what_matters_not_the_middle():
    from reel_engine import render

    import re

    focus = [[k * 0.5, 0.82] for k in range(8)]
    crop, _ = render.framing(_src(), _item(), [], focus)
    left = float(re.findall(r"([0-9]\.[0-9]+)\)*\*iw'", crop)[-1])  # where the window settles
    assert left > 0.5  # a centred window would start at 0.34


# ------------------------------------------------------------------ styles

def test_a_style_holds_the_reel_to_its_rules():
    from reel_engine import styles

    words = words_of("this is a calm talk about breathing and being present every day")
    from reel_engine import typekits

    d = director(style="calm", type_kit="comic_burst", mood="energetic", story=[clip(w0=0, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    calm = styles.get("calm")
    assert brief.style == "calm" and brief.type_kit in {k["id"] for k in typekits.for_style("calm")} and brief.mood in calm["moods"]
    assert brief.caption_looks == calm["caption_looks"]
    assert styles.get("nonsense")["name"] == styles.catalog()["default"]


def test_a_style_caps_its_effects():
    from reel_engine import effects

    words = words_of(" ".join(f"word{k}" for k in range(120)), gap=0.4)
    d = director(story=[clip(w0=0, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 200.0})
    picks = [fx(name="doodle", w0=k, w1=k + 3, choice="crown", target="face_top") for k in (5, 25)] + \
            [fx(name="glass_type", w0=k, w1=k + 3, texts=["Stay calm"]) for k in (45, 65)]
    assert len(effects.compile_effects(picks, words, items, most=1)) == 1
    # Four slots, but the second quiet effect (glass_type again) is refused: a reel is never mostly quiet effects.
    placed = {(g.data["effect"], g.start) for g in effects.compile_effects(picks, words, items, most=4)}
    assert len(placed) == 3 and sum(1 for name, _ in placed if name in effects.QUIET) == 1


def test_the_reviewer_can_enlarge_an_item_inside_the_frame():
    from reel_engine.review import Action, apply

    plan = EditPlan(duration=10, graphics=[GraphicItem(id="g1", kind="two", start=1, end=3, box=[900, 100, 170, 80])])
    assert apply(plan, [Action(id="g1", action="enlarge", why="too small")]) == 1
    x, y, w, h = plan.graphics[0].box
    assert w == 204 and h == 96 and x + w <= 1080 and y >= 0


def test_a_split_screen_that_would_lose_a_face_cuts_to_the_talker():
    from reel_engine import render

    # The right-hand person leans far out of their half for most of the shot.
    rows = [[k * 0.25, x, 0.4, 0.09, 0.15, talk] for k in range(12)
            for x, talk in ((0.3, 0.03), (0.72 if k < 3 else 0.98, 0.025))]
    crop, _ = render.framing(_src(), _item(), rows)
    assert "vstack" not in crop


# ------------------------------------------------------------------ several reels, hooks, proofreading, review history

def test_a_long_video_gives_a_reel_per_ninety_seconds_of_speech_within_the_cap():
    from reel_engine import moments

    minute = [Word(i=k, src=0, t0=k * 0.5, t1=k * 0.5 + 0.45, text="word") for k in range(120)]
    ten = [Word(i=k, src=0, t0=k * 0.5, t1=k * 0.5 + 0.45, text="word") for k in range(1200)]
    hour = [Word(i=k, src=0, t0=k * 0.5, t1=k * 0.5 + 0.45, text="word") for k in range(7200)]
    assert moments.reels_for(minute, 8) == 1
    assert moments.reels_for(ten, 10) == 6  # ten minutes (9 of speech) gives six reels
    assert moments.reels_for(hour, 10) == 10 and moments.reels_for(hour, 3) == 3
    assert moments.reels_for([], 8) == 1


def test_the_best_moment_always_makes_a_reel_and_weak_ones_do_not():
    from reel_engine.moments import Moment, worth_a_reel

    def m(score: float) -> Moment:
        return Moment(start=0, end=1, hook=0, payoff=1, title="t", headline="Why does this work?", hook_score=score,
                      payoff_score=score, standalone_score=score, why="")

    found = [(m(8), 0, 30, 0), (m(6.2), 40, 70, 0), (m(5), 80, 110, 0), (m(7), 120, 150, 0)]
    assert [f[1] for f in worth_a_reel(found, 8)] == [0, 40, 120]
    assert [f[1] for f in worth_a_reel(found, 2)] == [0, 40]
    assert worth_a_reel([(m(3), 0, 30, 0)], 8)  # one weak moment still gives the one reel


def test_a_talking_reel_opens_on_a_hook_headline_not_one_word():
    words = words_of("athletes remove body hair for two reasons and the second one surprised me a lot")
    d = director(hooks=[DHook(clip=clip(w0=0, w1=4), word="HAIR", why="")], hook_text="HAIR",
                 story=[clip(w0=5, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0, "Athletes body hair kyun hatate hain?")
    assert brief.hook_text == "Athletes body hair kyun hatate hain?"
    items = comp.video_track(d, brief, words, [], {0: 60.0})
    hooks = [g for g in comp.graphics_track(d, brief, words, items, []) if g.why == "hook word"]
    assert len(hooks) == 1 and hooks[0].kind == "hook" and hooks[0].data["text"] == brief.hook_text
    # One generic word is never a headline: the director's own (if it reads as one) or none.
    assert comp.hook_text("HAIR", "Why athletes shave their legs") == "Why athletes shave their legs"
    assert comp.hook_text("HAIR", "ENERGY") == ""


def test_proofreading_fixes_misheard_words_one_for_one(monkeypatch):
    from clients import ai
    from reel_engine import proof

    words = words_of("what the hell is this world the has happened to my pointy basis plan today")

    class Fake:
        async def chat_json(self, messages, schema, **kw):
            return schema(fixes=[proof.Fix(id=5, word="hell"), proof.Fix(id=11, word="day to day"), proof.Fix(id=99, word="x")])

    monkeypatch.setattr(ai, "get_text_client", lambda **kw: Fake())
    assert asyncio.run(proof.proofread(words, "hi")) == 1
    assert words[5].text == "hell" and words[11].text == "pointy"  # a multi-word fix would shift timing: refused


def test_a_later_review_hears_its_last_scores_and_the_changes():
    from reel_engine.plan import LayerScore, Review
    from reel_engine.review import Action, since

    note = since(Review(scores=[LayerScore(layer="hook", score=5)], overall=5.0),
                 [Action(id="c3", action="move", why=""), Action(id="c4", action="keep", why="")])
    assert "hook 5" in note and "c3: move" in note and "c4" not in note


def test_captions_keep_to_their_lanes():
    from reel_engine.layout import CAPTION_LANES

    detail = np.zeros((170, 96), np.float32)
    detail[110:150, :] = 1.0  # hands moving across the low lane
    top = free_top([80, 1360, 920, 210], [], detail, 1360, CAPTION_LANES)
    assert top in CAPTION_LANES and top != 1360


def test_a_thing_with_no_photo_pops_in_as_an_object_beside_the_speaker():
    from reel_engine.pipeline import add_photo_cards
    from reel_engine.plan import AssetRef, CaptionLine, InsertItem

    icon = AssetRef(id="lungs", kind="icon", path="lungs.png", licence="MIT", source="kit")
    plan = EditPlan(duration=10, inserts=[InsertItem(id="i0", kind="photo", start=2, end=4, asset=icon, label="Lungs", style="object")],
                    graphics=[GraphicItem(id="g0", kind="two", start=2.5, end=3.5), GraphicItem(id="g1", kind="list", start=6, end=8)],
                    captions=[CaptionLine(id="c0", start=2, end=4, lead="breathe", keyword="deep")])
    add_photo_cards(plan)
    objects = [g for g in plan.graphics if g.kind == "object"]
    assert len(objects) == 1 and objects[0].asset.id == "lungs" and objects[0].data["text"] == "Lungs"
    assert not plan.inserts and [g.id for g in plan.graphics if g.kind != "object"] == ["g1"]
    assert len(plan.captions) == 1  # the captions carry on beside it



# ------------------------------------------------------------------ type kits

def test_every_type_kit_font_is_declared_for_the_renderer_and_shipped():
    import re

    from reel_engine import typekits

    css = "".join((Path(__file__).resolve().parents[1] / "beats" / "renderer" / name).read_text() for name in ("fonts.css", "beats.css"))
    declared = set(re.findall(r'font-family: "([^"]+)"; (?:font-weight: [^;]+; )?src: url\("([^"]+)"\)', css))
    assert typekits.fonts() <= {family for family, _ in declared}
    fonts = Path(__file__).resolve().parents[1] / "static" / "motion" / "fonts"
    assert all((fonts / Path(url).name).exists() for _, url in declared)
    styles_ = {"podcast", "education", "business", "calm", "vlog", "hype", "food"}
    assert all(len(typekits.for_style(s)) >= 6 for s in styles_)  # every style has real choice


def test_reels_of_one_video_never_share_a_type_kit():
    from reel_engine import typekits

    taken: set[str] = set()
    words = words_of("money habits that quietly make you poor every single month")
    picks = []
    for n in range(6):
        d = director(style="business", type_kit="oswald_red", story=[clip(w0=0, w1=len(words) - 1)])
        brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0, taken=taken, seed=f"reel{n}")
        picks.append(brief.type_kit)
    assert picks[0] == "oswald_red" and len(set(picks)) == 6
    assert all(k in {kit["id"] for kit in typekits.for_style("business")} for k in picks)


def test_a_kit_draws_from_variables_and_takes_its_accent_from_the_footage():
    from reel_engine import typekits

    title = typekits.spec("playfair_gold", "title")
    assert title["classes"] == "treat-underline lead-spaced" and title["vars"]["--key-font"] == '"Playfair"'
    assert typekits.spec("clean_underline", "text", "#33aaff")["vars"]["--accent"] == "#33aaff"
    red = np.zeros((64, 64, 3), np.uint8)
    red[:] = (30, 30, 220)  # BGR: a red set
    accent = typekits.palette_accent([red])
    assert accent.startswith("#ff") and accent != typekits.FALLBACK_ACCENT
    assert typekits.palette_accent([np.full((64, 64, 3), 128, np.uint8)]) == typekits.FALLBACK_ACCENT


def test_an_accent_that_matches_the_footage_gives_way_to_a_readable_one():
    from reel_engine import typekits

    orange_robe = "#ff7a1f"
    assert typekits.spec("fraunces_soft", "text", orange_robe)["vars"]["--accent"] == "#ffffff"  # peach on orange: white
    assert typekits.spec("syne_art", "text", "#ff40d0")["vars"]["--accent"] == "#ffd36e"         # pink on pink: its gold
    assert typekits.spec("lexend_blue", "text", orange_robe)["vars"]["--accent"] == "#4da3ff"    # blue on orange reads
    assert typekits.spec("amber_block", "text", typekits.FALLBACK_ACCENT)["vars"]["--accent"] == "#ffb020"


# ------------------------------------------------------------------ explainer scenes

def scene(**kw):
    from reel_engine.scenes import DActor, DScene

    base = dict(shot="reveal", world="sky", w0=-1, w1=-1, actors=[DActor(show="cloud", label="")], number="", ratio=0.0,
                direction="none", place="", lat=0.0, lon=0.0, why="")
    return DScene(**{**base, **kw})


def test_scene_actors_use_a_built_form_when_one_fits_else_the_kit():
    from reel_engine.scenes import form_of

    assert form_of("Raindrop") == "drop" and form_of("warm air") == "heat" and form_of("water droplets") == "droplet"
    assert form_of("clouds") == "cloud" and form_of("lungs") is None


def test_a_scene_label_never_shows_a_figure_that_was_not_said():
    from reel_engine.scenes import proven

    assert proven("5 LAKH KG", "a cloud holds 500000 kg or 5 lakh kg of water") == "5 LAKH KG"
    assert proven("7 LAKH KG", "a cloud holds 5 lakh kg") == ""
    assert proven("5 LAKH KG", "ek cloud mein paanch lakh kilo") == "5 LAKH KG"  # said in words: cannot be checked
    assert proven("५ लाख", "बादल में 5 लाख किलो") == "५ लाख"


def test_scenes_keep_off_the_opening_face_and_each_other_within_their_length(monkeypatch):
    from reel_engine import scenes
    from reel_engine.plan import VideoItem

    words = words_of(" ".join(f"w{i}" for i in range(60)))
    items = [VideoItem(id="v0", src=0, t0=0, t1=3, out0=0, out1=3, role="hook"),
             VideoItem(id="v1", src=0, t0=3, t1=21, out0=3, out1=21)]
    asked = [scene(w0=1, w1=4), scene(w0=3, w1=8), scene(w0=10, w1=40), scene(w0=12, w1=14), scene(w0=30, w1=33, shot="many")]
    spots = scenes.placed(asked, items, words)
    # w0=1 would cut away before the face is seen; w0=3 opens on the hook's line; w0=12 overlaps the scene before it
    assert [s.w0 for _, _, s in spots] == [3, 10, 30]
    lo, hi = scenes.catalog()["seconds"]
    assert all(lo - 0.01 <= end - start <= hi + 0.01 for start, end, _ in spots)


def test_a_scene_takes_its_stretch_from_photos_and_story_graphics_but_not_captions():
    from reel_engine.plan import AssetRef, CaptionLine, InsertItem
    from reel_engine.scenes import make_room

    made = AssetRef(id="s", kind="scene", path="x0.mov", licence="made", source="scene", made=True)
    photo = AssetRef(id="p", kind="photo", path="p.jpg", licence="cc0", source="openverse")
    drawn = [InsertItem(id="x0", kind="scene", start=4, end=7, asset=made)]
    plan = EditPlan(duration=20, inserts=[InsertItem(id="i0", kind="photo", start=5, end=6, asset=photo),
                                          InsertItem(id="i1", kind="photo", start=10, end=12, asset=photo)],
                    graphics=[GraphicItem(id="g0", kind="tag", start=5, end=6), GraphicItem(id="g1", kind="progress", start=0, end=20),
                              GraphicItem(id="g2", kind="list", start=12, end=14)],
                    captions=[CaptionLine(id="c0", start=4, end=6, lead="", keyword="heat")])
    make_room(plan, drawn)
    assert [i.id for i in plan.inserts] == ["x0", "i1"]
    assert [g.id for g in plan.graphics] == ["g1", "g2"] and len(plan.captions) == 1


def test_a_drawn_scene_keeps_its_colours_when_cut_to():
    from reel_engine.inserts import cutaway_cmd
    from reel_engine.plan import AssetRef, InsertItem

    item = InsertItem(id="x0", kind="scene", start=1, end=3, asset=AssetRef(id="s", kind="scene", path="x0.mov", licence="", source=""))
    assert "lut3d" not in " ".join(cutaway_cmd(item, Path("o.mp4"), Path("g.cube"), 30, 1080, 1920))
    item.kind = "broll"
    assert "lut3d" in " ".join(cutaway_cmd(item, Path("o.mp4"), Path("g.cube"), 30, 1080, 1920))


def test_director_prompt_lists_every_scene_shot_and_world():
    from reel_engine.scenes import catalog, prompt

    text = prompt()
    assert all(f"- {name} (" in text for name in catalog()["shots"]) and all(f"- {name}:" in text for name in catalog()["worlds"])


def test_every_built_form_is_drawn_by_the_renderer():
    from reel_engine.scenes import catalog

    js = (Path(__file__).resolve().parents[1] / "beats" / "renderer" / "scene.js").read_text()
    assert all(re.search(rf"\b{form}: \(", js) or f"FORMS.{form} =" in js for form in catalog()["forms"])
    assert all(f"{shot}(" in js or f"SHOTS.{shot} =" in js for shot in catalog()["shots"])
    assert all(f"{world}: (" in js for world in catalog()["worlds"])


def test_a_stored_picture_is_reused_only_for_the_same_subject():
    from beats import kit
    from reel_engine.inserts import same_subject

    galaxy = AssetRecord(kind="photo", scope="global", words=["close", "finger", "hand", "pointing", "up"])
    bedroom = AssetRecord(kind="photo", scope="global", words=["bed", "bedroom", "dark", "pillow"])
    assert not same_subject(galaxy, kit.words_of("adult hand on chest discomfort"))
    assert not same_subject(galaxy, kit.words_of("analog clock face close up"))
    assert same_subject(bedroom, kit.words_of("bed pillow dark bedroom"))
    assert same_subject(bedroom, kit.words_of("dark bedroom"))


def test_a_scene_takes_a_strong_accent_and_needs_its_subject(monkeypatch):
    from reel_engine import icons, scenes
    from reel_engine.plan import VideoItem
    from reel_engine.scenes import DActor, vivid

    assert vivid("#ffffff") == "#ffb020" and vivid("#1e88f0") == "#1e88f0" and vivid("#202020") == "#ffb020"

    async def nothing(requests, **kw):
        return [None] * len(requests)

    monkeypatch.setattr(icons, "choose", nothing)
    words = words_of(" ".join(f"w{i}" for i in range(40)))
    items = [VideoItem(id="v0", src=0, t0=0, t1=14, out0=0, out1=14)]
    asked = [scene(shot="force", w0=5, w1=12, actors=[DActor(show="price tag", label="Price"), DActor(show="arrow", label="")]),
             scene(shot="force", w0=20, w1=27, actors=[DActor(show="droplets", label=""), DActor(show="heat", label="Heat")])]
    resolved = asyncio.run(scenes.resolve(asked, items, words))
    assert resolved[0][3] is None and [a["form"] for a in resolved[1][3]] == ["droplet", "heat"]


# ------------------------------------------------------------------ the 8+ pass: cuts, density, accuracy, captions

def test_a_phrase_said_twice_in_a_row_loses_its_first_saying():
    from reel_engine.listen import tag_fillers

    words = words_of("I think I think the heart is fine and fine")
    tag_fillers(words)
    assert [w.text for w in words if not w.filler] == ["I", "think", "the", "heart", "is", "fine", "and", "fine"]


def test_captions_only_use_readable_type_kits():
    from reel_engine import typekits

    assert all(typekits.legible(k) for k in typekits.for_style("podcast"))
    assert "serif_editorial" not in [k["id"] for k in typekits.for_style("podcast")]
    assert "serif_editorial" not in typekits.prompt()


def _line(cid: str, start: float, keyword: str) -> "CaptionLine":
    from reel_engine.plan import CaptionLine

    return CaptionLine(id=cid, start=start, end=start + 1.5, lead="the", keyword=keyword,
                       words=[{"text": "the", "key": False, "at": 0.0}, {"text": keyword, "key": True, "at": 0.4}])


def test_plain_talking_stretches_get_an_object_for_a_word_said(monkeypatch):
    from reel_engine import density, icons
    from reel_engine.plan import AssetRef

    plan = EditPlan(duration=20, graphics=[GraphicItem(id="h", kind="hook", start=0, end=2.5), GraphicItem(id="p", kind="progress", start=0, end=20),
                                           GraphicItem(id="g", kind="list", start=9, end=12)],
                    captions=[_line("c0", 3.0, "heart"), _line("c1", 5.2, "blood"), _line("c2", 13.0, "stress"), _line("c3", 16.5, "sleep")])
    assert density.gaps(plan) == [(2.5, 9), (12, 19.5)]

    async def pick(requests, **kw):
        return [AssetRef(id=q, kind="icon", path=f"{q}.png", licence="MIT", source="kit") if q != "stress" else None for q, _ in requests]

    monkeypatch.setattr(icons, "choose", pick)
    asyncio.run(density.fill(plan))
    added = [(g.asset.id, g.start) for g in plan.graphics if g.by == "density"]
    # one every few seconds, each at its word ("blood" comes too soon after "heart"; "stress" had no icon)
    assert added == [("heart", 3.4), ("sleep", 16.9)]


def test_the_accuracy_check_drops_a_picture_that_does_not_show_what_is_said(monkeypatch, tmp_path):
    from reel_engine import ai, check
    from reel_engine.plan import AssetRef, InsertItem, VideoItem

    photo = tmp_path / "p.jpg"
    import cv2
    cv2.imwrite(str(photo), np.full((64, 64, 3), 128, np.uint8))
    words = words_of("my hand on my chest hurts and the clock ticks")
    plan = EditPlan(duration=6, video=[VideoItem(id="v0", src=0, t0=0, t1=6, out0=0, out1=6)],
                    inserts=[InsertItem(id="i0", kind="photo", start=0.5, end=2, query="hand on chest", asset=AssetRef(id="a", kind="photo", path=str(photo), licence="cc0", source="x")),
                             InsertItem(id="i1", kind="photo", start=3, end=4.5, query="clock", asset=AssetRef(id="b", kind="photo", path=str(photo), licence="cc0", source="x"))])
    plan.audio.words = words
    asked = {}

    async def judge(system, text, jpegs, schema, max_tokens, step):
        asked.update(text=text, images=len(jpegs), step=step)
        return check.Verdicts(verdicts=[check.Verdict(item=0, shows=False, why="a galaxy"), check.Verdict(item=1, shows=True, why="clock")])

    monkeypatch.setattr(ai, "vision_json", judge)
    asyncio.run(check.check(plan))
    assert [i.id for i in plan.inserts] == ["i1"] and asked["images"] == 2 and asked["step"] == "reel_check"
    assert "hand on my chest" in asked["text"]


def test_the_check_answers_in_a_strict_schema():
    from reel_engine.check import Verdicts as CheckVerdicts

    assert _strict_compatible(CheckVerdicts.model_json_schema())


def test_a_reel_goes_on_without_its_scenes_when_the_renderer_fails(monkeypatch, tmp_path):
    from reel_engine import render, scenes
    from reel_engine.plan import Brief, VideoItem

    async def broken(*a, **kw):
        raise RuntimeError("graphics renderer timed out")

    monkeypatch.setattr(render, "_draw", broken)
    words = words_of(" ".join(f"w{i}" for i in range(40)))
    plan = EditPlan(video=[VideoItem(id="v0", src=0, t0=0, t1=14, out0=0, out1=14)],
                    brief=Brief(path="voice", audio_kind="voice", recipe="x", target_seconds=14))
    assert asyncio.run(scenes.build([scene(shot="many", w0=5, w1=12, actors=[scenes.DActor(show="droplets", label="")])], plan, words, tmp_path)) == []


def test_graphics_never_cover_a_face_or_the_headline_they_shrink_or_go(monkeypatch):
    from reel_engine import layout

    face = (300, 380, 780, 1000)  # a talking head filling the middle of the frame
    monkeypatch.setattr(layout, "look", lambda video, a, b: ([face], np.zeros((layout.DETAIL_H, layout.DETAIL_W), np.float32)))
    hook = GraphicItem(id="h", kind="hook", start=0, end=3)
    icon = GraphicItem(id="o", kind="object", start=0.1, end=2.5)
    checklist = GraphicItem(id="l", kind="list", start=5, end=9, data={"items": ["a", "b", "c", "d", "e"]})
    huge = GraphicItem(id="c", kind="chart", start=10, end=12, box=[0, 200, 1080, 1500])
    graphics = [icon, hook, checklist, huge]
    layout.place(graphics, [], "unused.mp4")
    kept = {g.id: g for g in graphics}
    assert "h" in kept  # the hook always stays
    assert "c" not in kept or kept["c"].box[2] < 1080  # a frame-filling chart is set smaller beside the face, or left out
    for g in kept.values():
        if g.kind in layout.OPTIONAL:
            assert layout.overlap(g.box, [face]) <= layout.CLEAR
    if "o" in kept:
        hx, hy, hw, hh = kept["h"].box
        assert layout.overlap(kept["o"].box, [(hx, hy, hx + hw, hy + hh)]) <= layout.CLEAR


@pytest.mark.parametrize("seen, ours", [("other", True), ("bottom", True), ("none", True), ("middle", False)])
def test_our_captions_step_aside_only_for_subtitles_across_the_picture(monkeypatch, seen, ours):
    from reel_engine import verify as verifying
    from reel_engine.plan import Source

    words = words_of("can afib cause a heart attack")
    d = director(burned_captions=True, caption_mode="none", hooks=[DHook(clip=clip(w0=0, w1=5), word="", why="question")])

    async def judge(*a, **kw):
        return Verdicts(best_hook=0, hook_why="", subtitles=seen, checks=[])

    monkeypatch.setattr(verifying, "strip", lambda *a: b"jpeg")
    monkeypatch.setattr(verifying, "vision_json", judge)
    asyncio.run(verifying.verify(d, [Source(index=0, name="a.mp4", path="a.mp4", kind="video")], words))
    assert (not d.burned_captions and d.caption_mode == "every_word") == ours


def test_the_director_designs_each_reels_type_and_a_broken_design_falls_back_to_a_kit():
    from reel_engine import typekits

    words = words_of("money habits that quietly make you poor")
    d = director(style="business", type_kit="oswald_red", story=[clip(w0=0, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0, seed="r0")
    assert brief.kit["key"]["font"] == "Unbounded" and brief.kit["treatment"] == "glow"
    made = typekits.spec(brief.type_kit, "text", kit=brief.kit)
    assert made["vars"]["--key-font"] == '"Unbounded"' and "treat-glow" in made["classes"]
    for broken in (dict(key_font="Comic Sans"), dict(accent="orange"), dict(lead_weight=300, lead_treatment="plain")):
        d = director(style="business", type_kit="oswald_red", story=[clip(w0=0, w1=len(words) - 1)], text_style=text_style(**broken))
        brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0, seed="r0")
        assert brief.kit == {} and brief.type_kit == "oswald_red"
    assert all(f in typekits.design_prompt() for f in ("Unbounded", "Inter", "glow"))


def test_a_long_take_is_reframed_about_every_two_seconds_between_words():
    words = words_of(" ".join(f"w{i}" for i in range(30)))  # ~10.5 s of continuous speech
    d = director(story=[clip(w0=0, w1=29, zoom="in")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 60.0})
    assert len(items) >= 4 and all(1.5 <= i.t1 - i.t0 <= comp.SUBSHOT_MAX + 0.6 for i in items)
    assert {i.zoom for i in items[1:]} >= {"punch"}  # tight and wide in turn
    starts = [w.t0 for w in words]
    ends = [w.t1 for w in words]
    for item in items[1:]:  # every cut falls in a gap between two words, never inside one
        assert not any(a < item.t0 < b for a, b in zip(starts, ends))


def test_every_visual_beat_lands_with_its_own_sound_and_none_smear(monkeypatch, tmp_path):
    from reel_engine import accents, sound
    from reel_engine.plan import AssetRef, InsertItem, VideoItem

    picked = []

    def library(role, n, seed=0):
        picked.append(role)
        return AssetRef(id=f"sfx.{role}.{n}", kind="sfx", path=f"{role}.wav", licence="", source="lib")

    monkeypatch.setattr(accents, "sound", library)
    plan = EditPlan(duration=20, video=[VideoItem(id="v0", src=0, t0=0, t1=5, out0=0, out1=5), VideoItem(id="v1", src=0, t0=5, t1=8, out0=5, out1=8, zoom="punch"),
                                        VideoItem(id="v2", src=0, t0=8, t1=20, out0=8, out1=20, role="payoff")],
                    graphics=[GraphicItem(id="o", kind="object", start=2, end=3), GraphicItem(id="k", kind="keyword", start=2.2, end=3),
                              GraphicItem(id="s", kind="statement", start=10, end=12)],
                    inserts=[InsertItem(id="x", kind="scene", start=14, end=17, asset=AssetRef(id="s", kind="scene", path="s.mov", licence="", source=""))])
    hits = asyncio.run(sound.effects(plan, Scout(LocalAssetStore(tmp_path), "o", tmp_path)))
    times = [t for t, _, _ in hits]
    assert all(b - a >= sound.MIN_SPACING for a, b in zip(times, times[1:]))
    assert {"click" if "click" in r.id else r.id.split(".")[1] for _, r, _ in hits} >= {"impact", "whoosh", "transition", "riser"}
    assert all(gain < 0.35 for _, _, gain in hits)  # always well under the voice


def test_photo_requests_search_stock_first_and_show_the_best_of_every_source(monkeypatch, tmp_path):
    from broll.sources import photos
    from broll.sources.base import StockClip
    from reel_engine import inserts

    def fake(name, licence, n=3):
        async def search(self, query, per_page):
            return [StockClip(source=name, source_id=f"{name}{k}", source_url="", download_url=f"https://x/{name}{k}.jpg", title=query,
                              tags=[], width=1080, height=1920, duration_s=0, license_code=licence, license_url=None) for k in range(n)]
        return search

    monkeypatch.setattr(photos.PexelsPhotos, "search", fake("pexels", "pexels"))
    monkeypatch.setattr(photos.PixabayPhotos, "search", fake("pixabay", "pixabay"))
    monkeypatch.setattr(photos.WikimediaPhotos, "search", fake("wikimedia", "cc0"))
    monkeypatch.setattr(photos.OpenversePhotos, "search", fake("openverse", "cc_by"))  # not a licence we take
    monkeypatch.setattr(photos.NasaPhotos, "search", fake("nasa", "public_domain", 0))
    got = []

    async def download(url, target, limit):
        got.append(url.rsplit("/", 1)[-1])
        target.write_bytes(b"x" * 2048)
        return target

    monkeypatch.setattr(inserts, "_download", download)
    picked = asyncio.run(inserts._candidates("photo", "gardener laying sod", tmp_path, 4))
    assert [p[1]["source"] for p in picked] == ["pexels", "pixabay", "wikimedia", "pexels"]
    assert not any("openverse" in g for g in got)


def test_one_persons_skin_matches_across_cuts_and_a_yellow_cast_eases_without_changing_brightness():
    from reel_engine.render import SKIN_LIMIT, skin_match

    warm, cool, usual = np.array([200, 160, 110.0]), np.array([190, 160, 140.0]), np.array([200, 162, 128.0])
    gains = skin_match([warm, cool, usual, None])
    matched = [f * g for f, g in zip((warm, cool, usual), gains)]
    spread = lambda faces: np.ptp([f[2] / f[0] for f in faces])  # noqa: E731
    assert spread(matched) < spread([warm, cool, usual])  # the shots move toward one skin colour
    assert all(abs(g.mean() - 1.0) < 1e-6 for g in gains) and np.allclose(gains[3], 1.0)
    assert all(SKIN_LIMIT[0] - 0.05 <= x <= SKIN_LIMIT[1] + 0.05 for g in gains for x in g)
    yellow = skin_match([np.array([210, 170, 100.0])] * 2)[0]
    assert yellow[2] > 1.0  # a reel whose skin reads yellow gets a little more blue


def test_no_icon_shows_twice_in_a_reel():
    from reel_engine.density import one_of_each
    from reel_engine.plan import AssetRef, CaptionLine

    car = AssetRef(id="obj.car", kind="icon", path="car.png", licence="MIT", source="kit")
    plan = EditPlan(duration=20, graphics=[GraphicItem(id="a", kind="object", start=1, end=2, asset=car),
                                           GraphicItem(id="b", kind="object", start=5, end=6, asset=car),
                                           GraphicItem(id="c", kind="tag", start=8, end=9, asset=car, data={"text": "Car"})],
                    captions=[CaptionLine(id="l", start=12, end=13, lead="a", keyword="car", icon=car)])
    assert one_of_each(plan) == 3
    assert [g.id for g in plan.graphics] == ["a", "c"] and plan.graphics[1].asset is None and plan.captions[0].icon is None


def test_a_ticker_band_starts_at_the_edge_and_a_poster_high_in_the_frame_is_not_one():
    from reel_engine.media import edge_band

    plain = np.full(360, 0.01)
    ticker = plain.copy()
    ticker[-40:] = 0.3          # lettering along the bottom edge
    poster = plain.copy()
    poster[60:100] = 0.3        # lettering in the top third, away from the edge
    assert 0.1 < edge_band(ticker, "bottom") < 0.16
    assert edge_band(poster, "top") is None and edge_band(plain, "bottom") is None


def test_captions_step_aside_while_the_hook_headline_is_up_and_statements_leave_the_face_clear():
    from reel_engine import layout

    words = words_of("why do investors buy high and sell low every single time the market moves")
    d = director(hook_text="Why do investors buy high?", hooks=[DHook(clip=clip(w0=0, w1=4), word="", why="question")],
                 story=[clip(w0=5, w1=len(words) - 1)])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 60.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    hook = next(g for g in graphics if g.kind == "hook")
    captions, _ = comp.captions_track(d, brief, words, items, graphics)
    assert captions and not any(c.start < hook.end - 0.05 and hook.start < c.end - 0.05 for c in captions)
    x, top, w, h = layout.default_box("statement")
    assert top >= 1100 and top + h <= layout.SAFE_BOTTOM  # a lower card: the face above it stays clear


def test_a_finished_reel_gets_a_cover_from_its_own_frames(tmp_path):
    import subprocess

    from reel_engine.media import cover

    reel = tmp_path / "reel.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=orange:s=270x480:d=2", "-pix_fmt", "yuv420p", str(reel)], check=True)
    image = cover(reel)
    assert image[:2] == b"\xff\xd8"  # a JPEG
    assert cover(tmp_path / "missing.mp4") == b""


def test_the_reels_board_cover_is_the_first_reel_then_a_planned_moment_then_a_footage_frame():
    import json as _json

    from edit_engine.model import EditProject
    from edit_engine.service import _cover_key

    def made(reels=None, premium=None) -> EditProject:
        return EditProject(reels=_json.dumps(reels or []), premium=_json.dumps(premium or {}))

    assert _cover_key(made([{"key": "r1.mp4", "thumb": "r1.jpg"}], {"planned": [{"thumb": "m0.jpg"}]})) == "r1.jpg"
    assert _cover_key(made([{"key": "r1.mp4"}], {"planned": [{"thumb": None}, {"thumb": "m1.jpg"}], "frames": ["f0.jpg"]})) == "m1.jpg"
    assert _cover_key(made(premium={"frames": ["f0.jpg"]})) == "f0.jpg"
    assert _cover_key(made()) is None

