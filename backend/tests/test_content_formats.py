"""AI-chosen short-form formats: persistence, serialisation, list overlays and auto B-roll."""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import clip_generation.service as clip_service
from clip_generation.hook import Hook
from clip_generation.model import GeneratedClip, VideoAnalysis
from clip_generation.schema import GeneratedClipResponse
from clip_generation.service import ClipService, _edit_choices, format_overlay
from subtitle_styling.ass_generator import TITLE_SECONDS, AssGenerator
from subtitle_styling.format_overlay import overlay_kind, place_format_items

ITEMS = [
    {"t": 12.0, "end": 19.0, "label": "Sleep eight hours", "rank": None},
    {"t": 22.0, "end": 29.0, "label": "Drink water", "rank": None},
    {"t": 31.0, "end": 38.0, "label": "Walk every day", "rank": None},
]


def _dialogues(ass: str) -> list[str]:
    return [line for line in ass.splitlines() if line.startswith("Dialogue:") and ",FormatOverlay," in line]


def _times(line: str) -> tuple[str, str]:
    fields = line[len("Dialogue: "):].split(",")
    return fields[1], fields[2]


def _y(line: str) -> int:
    return int(re.search(r"\\pos\(\d+,(\d+)\)", line).group(1))


class TestModel:
    def test_columns(self):
        assert GeneratedClip.__table__.c.content_format.type.length == 40
        assert GeneratedClip.__table__.c.content_format.nullable
        assert VideoAnalysis.__table__.c.content_format.type.length == 40

    def test_migration_follows_caption_styles(self):
        from importlib.util import module_from_spec, spec_from_file_location
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "20261002010000_add_content_format.py"
        spec = spec_from_file_location("add_content_format", path)
        migration = module_from_spec(spec)
        spec.loader.exec_module(migration)
        assert (migration.revision, migration.down_revision) == ("20261002010000", "20261001020000")


class TestPlacement:
    def test_items_follow_the_hook_and_skip_cut_pauses(self):
        placed = place_format_items(ITEMS, "listicle", 10.0, 40.0, Hook(50.0, 53.0), [(10.0, 20.0), (21.0, 40.0)])
        # 3 s of teaser first; the second span starts 10 s into the body, a second after its own start.
        assert [(p["start"], p["end"], p["number"], p["rank"]) for p in placed] == [
            (5.0, 14.0, 1, None), (14.0, 23.0, 2, None), (23.0, 30.0, 3, None),
        ]

    def test_a_bridge_moves_the_items_back(self):
        placed = place_format_items(ITEMS, "listicle", 10.0, 40.0, Hook(50.0, 53.0), gap=0.5)
        assert placed[0]["start"] == pytest.approx(5.5)

    def test_items_cut_out_or_outside_the_clip_are_dropped(self):
        items = [*ITEMS, {"t": 45.0, "end": 47.0, "label": "After the end"}, {"t": 20.2, "end": 20.8, "label": "In a cut"}]
        placed = place_format_items(items, "listicle", 10.0, 40.0, spans=[(10.0, 20.0), (21.0, 40.0)])
        assert [p["label"] for p in placed] == ["Sleep eight hours", "Drink water", "Walk every day"]

    def test_only_list_formats_with_two_items(self):
        assert place_format_items(ITEMS, "talking_head", 10.0, 40.0) == []
        assert place_format_items(ITEMS, None, 10.0, 40.0) == []
        assert place_format_items(ITEMS[:1], "listicle", 10.0, 40.0) == []
        assert place_format_items([{"t": "x", "label": "a"}, {"t": 12.0}], "listicle", 10.0, 40.0) == []

    def test_unranked_ranking_counts_down_to_the_top_pick(self):
        placed = place_format_items(ITEMS, "ranking", 10.0, 40.0)
        assert [p["rank"] for p in placed] == [3, 2, 1]

    def test_given_ranks_are_kept_and_duplicates_refilled(self):
        items = [{**ITEMS[0], "rank": 10}, {**ITEMS[1], "rank": 9}, {**ITEMS[2], "rank": 9}]
        assert [p["rank"] for p in place_format_items(items, "ranking", 10.0, 40.0)] == [10, 9, 3]

    def test_overlay_kinds(self):
        assert overlay_kind("listicle") == "list_counter"
        assert overlay_kind("ranking") == "rank_board"
        assert overlay_kind("broll") == overlay_kind(None) == "none"


class TestOverlayAss:
    def test_list_counter_shows_each_item_with_its_count(self):
        placed = place_format_items(ITEMS, "listicle", 10.0, 40.0)
        ass = AssGenerator().build_ass([], 10.0, 40.0, overlay="list_counter", overlay_items=placed)
        assert "Style: FormatOverlay,Montserrat," in ass
        texts = [line for line in _dialogues(ass) if line.endswith(("1/3", "2/3", "3/3"))]
        assert [_times(line) for line in texts] == [
            ("0:00:02.00", "0:00:12.00"), ("0:00:12.00", "0:00:21.00"), ("0:00:21.00", "0:00:28.00"),
        ]
        assert any(line.endswith("}Drink water") for line in _dialogues(ass))

    def test_list_counter_clears_the_title_card_and_captions(self):
        placed = place_format_items(ITEMS, "listicle", 0.0, 40.0)
        words = [{"start": 1.0, "end": 1.5, "text": "hello"}]
        ass = AssGenerator().build_ass(words, 0.0, 40.0, title="Three habits", overlay="list_counter", overlay_items=placed)
        title_top = round(0.07 * 1920)
        caption_y = round(0.76 * 1920)
        for line in _dialogues(ass):
            assert title_top + 100 < _y(line) < caption_y - 100

    def test_rank_board_fills_in_and_highlights_the_current_item(self):
        placed = place_format_items(ITEMS, "ranking", 10.0, 40.0)
        ass = AssGenerator().build_ass([], 10.0, 40.0, overlay="rank_board", overlay_items=placed)
        events = _dialogues(ass)
        slots = [line for line in events if re.search(r"\}\d\.$", line)]
        # Every slot shows from the first reveal to the end of the clip, best at the top.
        assert [line[-2:] for line in slots] == ["1.", "2.", "3."]
        assert all(_times(line) == ("0:00:02.00", "0:00:30.00") for line in slots)
        assert _y(slots[0]) < _y(slots[1]) < _y(slots[2])
        water = [line for line in events if line.endswith("}Drink water")]
        # Highlighted (dark ink on the accent) while it plays, then white for the rest of the clip.
        assert [_times(line) for line in water] == [("0:00:12.00", "0:00:21.00"), ("0:00:21.00", "0:00:30.00")]
        assert "\\1c&H00000000" in water[0] and "\\1c&H00FFFFFF" in water[1]
        # Drink water is rank 2 of a countdown, so it sits on the second slot.
        assert _y(water[0]) == _y(slots[1])
        assert all(int(re.search(r"\\pos\((\d+),", line).group(1)) > 1080 / 2 for line in events)

    def test_rank_board_keeps_off_a_stacked_seam(self):
        placed = place_format_items(ITEMS, "ranking", 0.0, 40.0)
        ass = AssGenerator().build_ass(
            [], 0.0, 40.0, title="Ranked", seams=[(0.0, 40.0, 0.5)], overlay="rank_board", overlay_items=placed,
        )
        seam_y = 960
        for line in _dialogues(ass):
            assert abs(_y(line) - seam_y) > 80

    def test_no_items_no_overlay(self):
        ass = AssGenerator().build_ass([], 0.0, 10.0, title="Plain", overlay="none", overlay_items=[])
        assert "FormatOverlay" not in ass
        assert TITLE_SECONDS == 5.0


class TestSavedChoices:
    def test_old_clips_cut_as_talking_heads(self):
        assert _edit_choices({"clip": {"layout_hint": "auto"}})["content_format"] == "talking_head"
        assert _edit_choices({"clip": {}}) == {}
        assert _edit_choices(None) == {}

    def test_format_and_evidence_are_kept(self):
        choices = _edit_choices({"clip": {"content_format": "reaction", "format_evidence": {"facecam": 0.8}}})
        assert choices["content_format"] == "reaction"
        assert choices["format_evidence"] == {"facecam": 0.8}
        assert _edit_choices({"clip": {"format_evidence": "junk"}})["format_evidence"] is None

    def test_format_overlay_arguments(self):
        clip = GeneratedClip(content_format="listicle")
        assert format_overlay(clip, {"clip": {"format_items": ITEMS}}) == {"content_format": "listicle", "format_items": ITEMS}
        assert format_overlay(clip, {}) == {"content_format": "listicle", "format_items": []}


def _service() -> ClipService:
    service = object.__new__(ClipService)
    service._s3 = SimpleNamespace(generate_presigned_url=lambda *a, **k: None)
    service._bucket = "bucket"
    return service


class TestSerialisation:
    def _clip(self, **overrides) -> GeneratedClip:
        values = dict(
            id="c1", project_id="p1", user_id="u1", title="Three habits", start_time=10.0, end_time=40.0,
            duration_seconds=33.0, hook_start=50.0, hook_end=53.0, score=80.0, status="completed",
            content_format="listicle", analysis_json=json.dumps({"clip": {"format_items": ITEMS}}),
        )
        return GeneratedClip(**{**values, **overrides})

    def test_clip_carries_its_format_and_items_on_its_own_timeline(self):
        data = _service()._serialize_clip(self._clip())
        assert data["content_format"] == "listicle"
        assert [(i["start"], i["number"]) for i in data["format_items"]] == [(5.0, 1), (15.0, 2), (24.0, 3)]
        response = GeneratedClipResponse.model_validate(data)
        assert response.content_format == "listicle" and response.format_items[1].label == "Drink water"

    def test_older_clip(self):
        data = _service()._serialize_clip(self._clip(content_format=None, analysis_json=None))
        assert data["content_format"] is None and data["format_items"] == []


class TestSaving:
    @pytest.mark.asyncio
    async def test_content_format_is_saved_and_items_kept_in_analysis(self, monkeypatch):
        created: dict = {}

        @asynccontextmanager
        async def session():
            yield None

        class Repo:
            def __init__(self, _session):
                pass

            async def create_clip(self, **kwargs):
                created.update(kwargs)
                return SimpleNamespace(s3_key=kwargs["s3_key"])

        monkeypatch.setattr(clip_service, "AsyncSessionLocal", session)
        monkeypatch.setattr(clip_service, "ClipRepository", Repo)
        clip = {
            "clip_id": "c1", "start_time": 10.0, "end_time": 40.0, "content_format": "ranking",
            "format_source": "ai", "format_evidence": {"face": 0.9}, "format_items": ITEMS,
            "s3_upload": {"s3_key": "k"},
        }
        await _service()._save_rendered_clips("p1", "u1", [clip], [], {}, {})
        assert created["content_format"] == "ranking"
        saved = json.loads(created["analysis_json"])["clip"]
        assert saved["format_source"] == "ai" and saved["format_items"][0]["label"] == "Sleep eight hours"


class TestCutRequest:
    @pytest.mark.asyncio
    async def test_format_reaches_the_cutter(self, monkeypatch, tmp_path):
        requests = []
        cut_file = tmp_path / "cut.mp4"
        cut_file.write_bytes(b"x")

        class Cutter:
            async def cut(self, request):
                requests.append(request)
                return SimpleNamespace(
                    rendered=True, output_files={"9:16": str(cut_file)}, errors=[], faces=[], crop_tracking={},
                    layout="follow", strategy="none", speaker_count=1, seams={},
                )

        monkeypatch.setattr(clip_service, "ClipCutter", Cutter)
        service = _service()
        service._output_dir = tmp_path
        clips = [
            {"clip_id": "a", "start_time": 0.0, "end_time": 10.0, "content_format": "voice_over",
             "format_evidence": {"face": 0.1}},
            {"clip_id": "b", "start_time": 10.0, "end_time": 20.0},
        ]
        await service.prepare_clip_outputs("p1", "source.mp4", clips, output_aspect_ratios=["9:16"])
        by_id = {r.clip_id: r for r in requests}
        assert (by_id["a"].content_format, by_id["a"].format_evidence) == ("voice_over", {"face": 0.1})
        assert (by_id["b"].content_format, by_id["b"].format_evidence) == ("talking_head", None)


class TestAutoBroll:
    def _clamp(self, monkeypatch, value):
        import pipeline.service as pipeline_service

        monkeypatch.setattr(pipeline_service, "require_caption_style", lambda *_: None)
        settings = {} if value == "unset" else {"broll": value}
        return pipeline_service._clamp_clip_settings(SimpleNamespace(max_clips_per_video=5), settings)["broll"]

    def test_unset_is_kept_apart_from_an_opt_out(self, monkeypatch):
        assert self._clamp(monkeypatch, True) is True
        assert self._clamp(monkeypatch, False) is False
        assert self._clamp(monkeypatch, "unset") is None
        assert self._clamp(monkeypatch, "yes") is None

    @pytest.mark.parametrize("broll, scope", [(True, "all"), (None, "formats"), (False, None)])
    def test_scope_follows_the_choice(self, broll, scope):
        from pipeline.service import broll_scope

        assert broll_scope({"broll": broll}) == scope
        assert broll_scope({}) == "formats"

    def test_density_follows_the_format(self):
        from broll.cutaways import broll_density

        assert broll_density(SimpleNamespace(content_format="voice_over")) == "heavy"
        assert broll_density(SimpleNamespace(content_format="green_screen")) == "light"
        assert broll_density(SimpleNamespace(content_format="talking_head")) == "normal"
        assert broll_density(SimpleNamespace(content_format=None)) == "normal"

    def test_heavy_allows_more_cover_than_light(self):
        from broll.planner import ClipWords, prompt, validate

        words = [{"start": i * 0.5, "end": i * 0.5 + 0.4, "word": f"w{i}"} for i in range(120)]
        raw = [{"from": i, "to": i + 7, "query": f"q{i}"} for i in range(6, 120, 9)]

        def cover(density):
            clip = ClipWords(words=words, spans=[(0.0, 60.0)], density=density)
            return sum(c.end - c.start for c in validate(raw, clip))

        assert cover("light") <= 0.25 * 60 < cover("heavy") <= 0.6 * 60
        assert "one cutaway per 5 seconds" in prompt([ClipWords(words=words, spans=[(0.0, 60.0)], density="heavy")])
        assert "per 5 seconds" not in prompt([ClipWords(words=words, spans=[(0.0, 60.0)])])
