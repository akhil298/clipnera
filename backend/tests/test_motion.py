from __future__ import annotations

import re

import pytest

from broll.planner import ClipWords
from clip_generation.hook import Hook
from motion.graphics import LayoutSpan, Placed, count_up, graphics_ass
from motion.icons import icon_for
from motion.moments import ClipMoments, Moment, reactions, validate
from motion.overlay import build_overlay
from motion.plan import BIG_NUMBER, CTA_CARD, LIST_CARD, REACTION, Cue, MotionPlan, dump_plan, load_plan
from motion.planner import LITE_MAX_CUES, plan_motion
from motion.sound import manifest, onset, sounds_for
from subtitle_styling.ass_generator import build_ass_file

SENTENCE = (
    "can I get twelve piece wings a large pickle some BBQ sauce and classic ranch "
    "use code KFSPEED for ten thousand dollars"
)


def _words(text: str = SENTENCE, step: float = 0.4, start: float = 0.0) -> list[dict]:
    return [{"word": w, "start": start + i * step, "end": start + i * step + 0.3} for i, w in enumerate(text.split())]


def _clip(text: str = SENTENCE, start: float = 0.0) -> ClipWords:
    words = _words(text, start=start)
    return ClipWords(words=words, spans=[(start, words[-1]["end"] + 1)])


ORDER = {"title": "The order", "items": [
    {"from": 3, "to": 5, "text": "12 pcs wings"}, {"from": 7, "to": 8, "text": "large pickle"},
    {"from": 10, "to": 11, "text": "BBQ sauce"}, {"from": 13, "to": 14, "text": "classic ranch"},
]}


class TestEvidence:
    def test_a_list_said_word_for_word_is_kept_with_its_beats(self):
        found = validate({"mood": "funny", "lists": [ORDER]}, _clip())
        (moment,) = found.moments
        assert moment.kind == "list" and moment.data["items"][0] == "12 pcs wings"
        assert moment.beats == pytest.approx((1.2, 2.8, 4.0, 5.2))
        assert found.mood == "funny"

    def test_one_unproven_item_drops_the_whole_list(self):
        bad = {**ORDER, "items": [*ORDER["items"][:3], {"from": 13, "to": 14, "text": "garlic mayo"}]}
        assert validate({"lists": [bad]}, _clip()).moments == []

    def test_a_short_list_is_not_a_list(self):
        assert validate({"lists": [{**ORDER, "items": ORDER["items"][:2]}]}, _clip()).moments == []

    def test_numbers_must_match_what_was_said(self):
        good = {"from": 19, "to": 21, "value": "$10,000", "label": "dollars"}
        wrong = {"from": 3, "to": 5, "value": "20", "label": "wings"}
        found = validate({"numbers": [good, wrong]}, _clip())
        assert [m.data["value"] for m in found.moments] == ["$10,000"]

    def test_names_and_codes_must_be_said(self):
        found = validate({
            "names": [{"from": 17, "to": 17, "kind": "brand", "text": "KFC"}],
            "ctas": [{"from": 15, "to": 17, "kind": "code", "text": "kfspeed"}],
        }, _clip())
        assert [(m.kind, m.data["text"]) for m in found.moments] == [("cta", "KFSPEED")]

    def test_unknown_moods_and_garbage_are_harmless(self):
        found = validate({"mood": "ecstatic", "lists": "nope", "numbers": [{"from": "x"}]}, _clip())
        assert found.mood == "neutral" and found.moments == []

    def test_reactions_come_from_loud_moments_without_speech(self):
        class Loud:
            def peaks(self):
                return [[0.9, 3.1], [9.5, 3.4], [12.0, 1.0]]

        words = _words("this is so funny", step=0.4)  # speech runs 0-1.5 s
        found = reactions(Loud(), words, [(0.0, 15.0)])
        assert [m.start for m in found] == [9.5]  # loud while talking is not a reaction; quiet is not loud


class TestIcons:
    @pytest.mark.parametrize("text, icon", [
        ("12 pcs wings", "🍗"), ("large pickle", "🥒"), ("BBQ sauce", ""), ("my goal", ""), ("ice cream", "🍦"),
    ])
    def test_icons_only_for_named_things(self, text, icon):
        assert icon_for(text) == icon


def _moments(*moments: Moment, mood: str = "funny") -> ClipMoments:
    return ClipMoments(mood=mood, moments=list(moments))


class TestPlanner:
    def test_a_list_gets_a_card_timed_to_its_items(self):
        plan = plan_motion(validate({"mood": "funny", "lists": [ORDER]}, _clip(start=10.0)), 10.0, 40.0, 30.0)
        (card,) = plan.cues
        assert card.kind == LIST_CARD and card.beats == pytest.approx([11.2, 12.8, 14.0, 15.2])
        assert card.start < card.beats[0] and card.end > card.beats[-1] + 1.0

    def test_when_graphics_clash_the_more_useful_one_wins(self):
        found = validate({"mood": "funny", "lists": [ORDER],
                          "numbers": [{"from": 19, "to": 21, "value": "$10,000", "label": ""}],
                          "ctas": [{"from": 15, "to": 17, "kind": "code", "text": "KFSPEED"}]}, _clip(start=10.0))
        assert [cue.kind for cue in plan_motion(found, 10.0, 40.0, 30.0).cues] == [CTA_CARD]

    def test_graphics_never_overlap_and_respect_the_budget(self):
        moments = [Moment("number", 5.0 + i * 1.5, 5.5 + i * 1.5, {"value": str(100 + i), "label": ""}) for i in range(8)]
        plan = plan_motion(_moments(*moments), 0.0, 20.0, 20.0)
        assert len(plan.cues) <= 3
        for a, b in zip(plan.cues, plan.cues[1:]):
            assert b.start >= a.end

    def test_the_light_plan_keeps_only_a_few_small_pops(self):
        found = validate({"mood": "funny", "lists": [ORDER],
                          "numbers": [{"from": 19, "to": 21, "value": "$10,000", "label": ""}],
                          "ctas": [{"from": 15, "to": 17, "kind": "code", "text": "KFSPEED"}]}, _clip(start=10.0))
        assert [cue.kind for cue in plan_motion(found, 10.0, 40.0, 30.0, lite=True).cues] == [BIG_NUMBER]
        moments = [Moment("number", 5.0 + i * 3, 5.5 + i * 3, {"value": str(100 + i), "label": ""}) for i in range(8)]
        assert len(plan_motion(_moments(*moments), 0.0, 40.0, 40.0, lite=True).cues) == LITE_MAX_CUES

    def test_nothing_in_the_opening_second(self):
        plan = plan_motion(_moments(Moment("number", 0.3, 0.8, {"value": "500", "label": ""})), 0.0, 20.0, 20.0)
        assert plan.cues == []

    def test_reaction_stickers_follow_the_mood(self):
        laugh = Moment("reaction", 5.0, 6.2, {"z": 3.0})
        assert plan_motion(_moments(laugh, mood="funny"), 0.0, 20.0, 20.0).cues[0].data["emoji"] == "😂"
        assert plan_motion(_moments(laugh, mood="sad"), 0.0, 20.0, 20.0).cues == []

    def test_plans_survive_storage(self):
        plan = MotionPlan("hype", [Cue(BIG_NUMBER, 3.0, 5.0, {"value": "200", "label": "kills"})])
        assert load_plan(dump_plan(plan)) == plan
        assert load_plan("not json") is None
        assert load_plan({"cues": [{"kind": "unknown", "start": 1, "end": 2}]}).cues == []


FOLLOW = LayoutSpan(0.0, 30.0, "follow", 0.0, ((0.28, 0.17, 0.45, 0.38),))
CROWDED = LayoutSpan(0.0, 30.0, "screen_with_speaker", 0.32,
                     ((0.12, 0.47, 0.32, 0.23), (0.63, 0.64, 0.21, 0.15), (0.81, 0.71, 0.26, 0.16)))
CARD = Placed(LIST_CARD, 2.0, 9.0, {"title": "The order", "items": [
    {"text": "12 pcs wings", "icon": "🍗"}, {"text": "large pickle", "icon": "🥒"}, {"text": "BBQ sauce", "icon": ""},
]}, [2.2, 3.6, 5.0])


class TestGraphics:
    def test_a_card_goes_under_the_face(self):
        drawn: list[Placed] = []
        ass = graphics_ass([CARD], [FOLLOW], 1080, 1920, 0.0, drawn=drawn)
        assert ass and drawn == [CARD]
        assert "THE ORDER" in ass and "large pickle" in ass

    def test_a_card_that_would_cover_a_face_is_left_out(self):
        drawn: list[Placed] = []
        assert graphics_ass([CARD], [CROWDED], 1080, 1920, 0.0, drawn=drawn) is None
        assert drawn == []

    def test_cards_stay_off_shown_content(self):
        open_cell = LayoutSpan(0.0, 30.0, "screen_with_speaker", 0.5, ())
        ass = graphics_ass([Placed(BIG_NUMBER, 2.0, 4.0, {"value": "$500", "label": ""})], [open_cell], 1080, 1920, 0.0)
        tops = [int(y) for _, y in re.findall(r"\\pos\((\d+),(\d+)\)", ass)]
        assert tops and min(tops) > 0.5 * 1920

    def test_figures_count_up_and_land_exactly(self):
        steps = count_up("$10,000")
        assert steps[-1] == "$10,000" and steps[0].startswith("$") and len(steps) > 5
        assert count_up("3x") == ["3x"]


class TestSound:
    def test_every_sound_exists_and_lands_on_its_event(self):
        assert {"pop", "click", "whoosh_short", "ding", "cash", "tick"} <= manifest().keys()
        sounds = sounds_for([CARD, Placed(BIG_NUMBER, 12.0, 14.0, {"value": "$500", "label": ""})])
        names = [s.name for s in sounds]
        assert names.count("click") == 3 and "cash" in names
        click = next(s for s in sounds if s.name == "click")
        assert onset(click) == pytest.approx(click.at - manifest()["click"]["peak"])

    def test_a_reaction_pops(self):
        assert [s.name for s in sounds_for([Placed(REACTION, 5.0, 6.0, {"emoji": "😂"})])] == ["pop"]


class TestOverlay:
    def test_cues_move_past_the_hook_and_its_bridge(self):
        plan = MotionPlan("funny", [Cue(LIST_CARD, 12.0, 19.0, CARD.data, [12.2, 13.6, 15.0])])
        hook = Hook(30.0, 33.0)
        overlay = build_overlay(plan, [{"start": 0, "end": 3, "kind": "follow", "faces": []},
                                       {"start": 3, "end": 30, "kind": "follow", "faces": [[0.28, 0.17, 0.45, 0.38]]}],
                                10.0, 40.0, hook, None, gap=0.5, width=1080, height=1920, title_seconds=5.0)
        # Body second 2 plays at 3 (hook) + 0.5 (bridge) + 2.
        assert overlay.quiet == [(pytest.approx(5.5), pytest.approx(12.5))]
        assert "click" in [s.name for s in overlay.sounds]

    def test_a_cue_cut_out_of_the_clip_is_dropped(self):
        plan = MotionPlan("funny", [Cue(BIG_NUMBER, 15.0, 17.0, {"value": "900", "label": ""})])
        assert build_overlay(plan, [], 10.0, 30.0, None, [(10.0, 14.0), (20.0, 30.0)], 0.0, 1080, 1920, 0.0) is None

    def test_captions_step_aside_while_a_card_is_up(self, tmp_path):
        words = [{"text": w, "start": 10.0 + i * 0.5, "end": 10.4 + i * 0.5}
                 for i, w in enumerate("one two three four five six seven eight nine ten".split())]
        loud = open(build_ass_file(words, 10.0, 16.0, output_path=str(tmp_path / "a.ass"))).read()
        quiet = open(build_ass_file(words, 10.0, 16.0, output_path=str(tmp_path / "b.ass"), quiet=[(0.0, 2.6)])).read()
        assert "ONE" in loud.upper() and "ONE" not in quiet.upper()
        assert "TEN" in quiet.upper()
