from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from beats import kit
from beats.compose import _sounds, caption_quiet
from beats.grade import GRADES, write_cube
from beats.plan import BEHIND, CARD, COUNT_UP, KEYWORD, LIST, NAME, STATEMENT, Beat, BeatPlan, dump_plan, load_plan
from beats.planner import Body, _Beat, _Item, pace, prove
from content_intelligence.edit_plan import _dropped


def _words(text: str, step: float = 0.4) -> list[dict]:
    return [{"word": w, "start": i * step, "end": i * step + step * 0.8} for i, w in enumerate(text.split())]


def _raw(kind: str, first: int, last: int, text: str = "", **fields) -> _Beat:
    base = {"label": "", "place": "beside", "items": [], "mark": "none", "visual": "", "trend": "none", "why": "test"}
    return _Beat(kind=kind, first=first, last=last, text=text, **{**base, **fields})


WORDS = _words("When I was earning 27,000 per month every rupee meant so much. No plan, no direction, no results.")


class TestProve:
    def test_a_figure_said_digit_for_digit_counts_up(self):
        beat = prove(_raw(COUNT_UP, 4, 6, "₹27,000", label="per month"), WORDS)
        assert beat is not None and beat.kind == COUNT_UP
        assert beat.data == {"prefix": "₹", "number": "27,000", "suffix": "", "label": "per month"}
        assert beat.start == pytest.approx(WORDS[4]["start"] - 0.08)

    def test_a_figure_nobody_said_is_dropped(self):
        assert prove(_raw(COUNT_UP, 4, 6, "₹30,000"), WORDS) is None

    def test_a_list_builds_on_each_item_and_needs_every_item_said(self):
        items = [_Item(first=12, last=13, text="No plan"), _Item(first=14, last=15, text="no direction"),
                 _Item(first=16, last=17, text="no results")]
        beat = prove(_raw(LIST, 12, 17, items=items, mark="cross", place="panel"), WORDS)
        assert beat is not None and beat.data["items"] == ["No plan", "no direction", "no results"]
        assert beat.steps == [round(WORDS[i]["start"], 3) for i in (12, 14, 16)]
        invented = [*items[:2], _Item(first=16, last=17, text="no money")]
        assert prove(_raw(LIST, 12, 17, items=invented), WORDS) is None

    def test_a_keyword_must_be_the_words_themselves(self):
        assert prove(_raw(KEYWORD, 7, 8, "every rupee", place="behind"), WORDS).place == BEHIND
        assert prove(_raw(KEYWORD, 7, 8, "every paisa"), WORDS) is None

    def test_a_statement_is_a_card(self):
        beat = prove(_raw(STATEMENT, 7, 11, "every rupee meant so much"), WORDS)
        assert beat is not None and beat.place == CARD

    def test_a_logo_without_its_file_becomes_a_name(self, monkeypatch):
        monkeypatch.setattr(kit, "logo", lambda name: None)
        words = _words("I ordered from Swiggy yesterday")
        assert prove(_raw("logo", 3, 3, "Swiggy"), words).kind == NAME

    def test_word_ids_out_of_range_are_dropped(self):
        assert prove(_raw(KEYWORD, 50, 52, "rupee"), WORDS) is None


class TestPace:
    def _beat(self, kind: str, start: float, end: float, place: str = "beside") -> Beat:
        return Beat(kind=kind, start=start, end=end, place=place)

    def test_overlaps_lose_to_the_more_useful_kind(self):
        kept = pace([self._beat(KEYWORD, 2.0, 3.5), self._beat(COUNT_UP, 2.5, 4.0)], Body([(0.0, 20.0)]))
        assert [b.kind for b in kept] == [COUNT_UP]

    def test_nothing_in_the_opening_and_nothing_outside_the_body(self):
        body = Body([(10.0, 20.0)])
        kept = pace([self._beat(KEYWORD, 10.2, 11.0), self._beat(KEYWORD, 19.0, 21.0), self._beat(KEYWORD, 12.0, 13.0)], body)
        assert [b.start for b in kept] == [12.0]

    def test_cards_are_spaced_out(self):
        kept = pace([self._beat(STATEMENT, 2.0, 3.5, CARD), self._beat(STATEMENT, 4.0, 5.5, CARD)], Body([(0.0, 30.0)]))
        assert len(kept) == 1

    def test_the_budget_follows_the_clip_length(self):
        beats = [self._beat(KEYWORD, 1.0 + 1.2 * i, 1.9 + 1.2 * i) for i in range(10)]
        assert len(pace(beats, Body([(0.0, 7.2)]))) == 3


class TestPlanStorage:
    def test_round_trip_keeps_known_kinds_only(self):
        plan = BeatPlan(theme="dark", beats=[Beat(kind=COUNT_UP, start=1.0, end=2.0)])
        stored = dump_plan(plan)
        stored["beats"].append({"kind": "hologram", "start": 0, "end": 1})
        loaded = load_plan(json.dumps(stored))
        assert loaded.theme == "dark" and [b.kind for b in loaded.beats] == [COUNT_UP]


class TestFinishHelpers:
    def _clip(self, beats: list[Beat]) -> SimpleNamespace:
        return SimpleNamespace(analysis_json=json.dumps({"beats": dump_plan(BeatPlan(beats=beats))}),
                               edit_spans=None, start_time=10.0, end_time=40.0)

    def test_captions_step_aside_only_under_cards_and_panels(self):
        clip = self._clip([Beat(kind=STATEMENT, start=12.0, end=14.0, place=CARD), Beat(kind=KEYWORD, start=20.0, end=21.0)])
        assert caption_quiet(clip, None) == [(2.0, 4.0)]

    def test_sounds_land_on_each_list_item(self):
        item = SimpleNamespace(start=5.0, steps=[0.2, 0.8, 1.4], behind=False, beat=Beat(kind=LIST, start=0, end=1))
        names = [(s.name, round(s.at, 2)) for s in _sounds([item])]
        assert names[0] == ("whoosh_short", 5.03)
        assert [at for name, at in names if name == "click"] == [5.25, 5.85, 6.45]

    def test_every_grade_writes_a_full_cube(self, tmp_path):
        for name, grade in GRADES.items():
            path = tmp_path / f"{name}.cube"
            write_cube(grade, path, size=5)
            lines = path.read_text().splitlines()
            assert lines[1] == "LUT_3D_SIZE 5" and len(lines) == 2 + 125


class TestTighten:
    def test_stutters_hesitations_and_earlier_takes_are_dropped(self):
        words = _words("I I think um this works. The plan is simple and clear. The plan is simple and clear.")
        dropped = _dropped(words)
        assert {0, 3} <= dropped
        assert set(range(6, 12)) <= dropped
        assert not dropped & set(range(12, 18))
