"""The reel engine's decisions that must hold for every reel: audio path, speech tightening, speeds, spacing,
captions, placement, the asset loop and the schemas the models answer in."""

from __future__ import annotations

import asyncio
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
    base = dict(audio_view="voice", recipe="creator_advice", target_seconds=30, title_lead="", title_text="", cta="",
                caption_mode="every_word", music="bed", mood="upbeat", sections=[], hooks=[], story=[], beats=[], keywords=[],
                drop_word=-1, spelling=[], notes="")
    return DirectorPlan(**{**base, **kw})


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


def test_captions_step_aside_for_a_graphic_and_skip_weak_keywords():
    words = words_of("but we have been working together really well up here")
    d = director(story=[clip(w0=0, w1=len(words) - 1)], beats=[beat(kind="two", w0=4, w1=5, lead="working", text="together")])
    brief, _ = comp.brief_of(d, AudioReport(kind="voice", words=words), 0)
    items = comp.video_track(d, brief, words, [], {0: 20.0})
    graphics = comp.graphics_track(d, brief, words, items, [])
    captions, _ = comp.captions_track(d, brief, words, items, graphics)
    two = next(g for g in graphics if g.kind == "two")
    assert all(not (two.start < c.end and c.start < two.end) for c in captions)
    assert all(c.keyword.lower() not in comp.WEAK for c in captions)
