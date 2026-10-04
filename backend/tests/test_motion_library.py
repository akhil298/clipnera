from __future__ import annotations

import json

import pytest

from clients.ai.base import ToolCall
from editor.agent_tools import EDITOR_TOOLS
from motion_library import catalog
from motion_library.catalog import find_assets, load_assets

CLEARED = {"code": "original", "commercial_ok": True}


def _entry(id_: str, kind: str, category: str, keywords: list[str], **over) -> dict:
    return {
        "id": id_, "kind": kind, "category": category, "keywords": keywords, "description": "", "use_when": "",
        "files": {"video": f"{kind}s/{id_}.mp4"}, "width": 1080, "height": 1920, "fps": 30, "duration_s": 6,
        "transparent": False, "loops": True, "blend_mode": "screen", "license": CLEARED, **over,
    }


@pytest.fixture
def library(tmp_path, monkeypatch):
    entries = [
        _entry("light_leak_warm", "overlay", "light", ["light leak", "warm", "glow", "nostalgia"]),
        _entry("flash_white", "transition", "flash", ["flash", "cut", "impact"]),
        _entry("money_wings", "animated_emoji", "money", ["spend", "expense"]),
        _entry("bokeh_gold", "overlay", "light", ["bokeh", "gold"], license={"code": "unverified", "commercial_ok": None}),
        _entry("missing_file", "overlay", "light", ["ghost"]),
    ]
    for entry in entries[:-1]:
        path = tmp_path / entry["files"]["video"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    (tmp_path / "catalog.json").write_text(json.dumps({"assets": entries}))
    monkeypatch.setattr(catalog, "library_root", lambda: tmp_path)
    return tmp_path


class TestCatalog:
    def test_only_cleared_assets_with_files_are_offered(self, library):
        # An uncleared licence or a missing file must never reach a model's choices.
        assert {a.id for a in load_assets()} == {"light_leak_warm", "flash_white", "money_wings"}

    def test_search_ranks_the_closest_match_first(self, library):
        assert [a.id for a in find_assets("warm nostalgic glow")] == ["light_leak_warm"]
        assert find_assets("flash on the cut")[0].id == "flash_white"

    def test_plural_and_id_words_match(self, library):
        assert find_assets("expenses")[0].id == "money_wings"
        assert find_assets("money")[0].id == "money_wings"

    def test_kind_narrows_the_search(self, library):
        assert find_assets("flash", kind="overlay") == []
        assert [a.id for a in find_assets("flash", kind="transition")] == ["flash_white"]

    def test_nothing_matching_is_an_empty_result(self, library):
        assert find_assets("dancing pumpkin") == []
        assert find_assets("gold bokeh") == []

    def test_a_missing_library_is_empty_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(catalog, "library_root", lambda: tmp_path / "absent")
        assert load_assets() == ()
        assert find_assets("anything") == []


class TestAgentTool:
    @pytest.mark.asyncio
    async def test_a_match_is_returned_with_what_the_edit_needs(self, library):
        result = await EDITOR_TOOLS.call(None, ToolCall("1", "find_motion_asset", {"query": "warm glow", "kind": "overlay"}))
        reply = json.loads(result.content)
        assert reply["found"] is True
        assert reply["assets"][0]["id"] == "light_leak_warm"
        assert reply["assets"][0]["files"] == {"video": "overlays/light_leak_warm.mp4"}
        assert reply["assets"][0]["blend_mode"] == "screen"

    @pytest.mark.asyncio
    async def test_no_match_says_not_found_instead_of_failing(self, library):
        result = await EDITOR_TOOLS.call(None, ToolCall("1", "find_motion_asset", {"query": "explosion", "kind": "motion_graphic"}))
        reply = json.loads(result.content)
        assert result.is_error is False
        assert reply["found"] is False
        assert "motion graphic" in reply["message"]

    @pytest.mark.asyncio
    async def test_an_unknown_kind_is_refused(self, library):
        result = await EDITOR_TOOLS.call(None, ToolCall("1", "find_motion_asset", {"query": "x", "kind": "hologram"}))
        assert result.is_error is True
