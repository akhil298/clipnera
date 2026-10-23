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
                caption_mode="every_word", music="bed", text_style="punch", mood="upbeat", sections=[], hooks=[], story=[], beats=[],
                inserts=[], keywords=[], burned_captions=False,
                drop_word=-1, spelling=[], effects=[], notes="")
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
    result = asyncio.run(ai.vision_json("s", "t", [b"a", b"b", b"c", b"d"], Picks, 100))
    assert result.picks == [] and calls == [4, 2, 2, 0]


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
    single = comp.video_track(director(story=[clip(w0=0, w1=len(words) - 1)]), brief, words, [], {0: 60.0})
    assert effects.compile_effects([fx(name="zoom_through", w0=6, w1=6)], words, single) == []


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
    assert "at most 2 per reel" in text


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
    left = float(re.search(r"'\(([0-9.]+)\)\*iw'", crop).group(1))
    assert left > 0.5  # a centred window would start at 0.34
