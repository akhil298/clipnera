from __future__ import annotations

import pytest

from subtitle_styling.service import SubtitleStylingService


@pytest.mark.asyncio
async def test_get_style_presets():
    service = SubtitleStylingService()
    presets = await service.get_style_presets()
    assert len(presets) >= 1
    types = [p["style_type"] for p in presets]
    assert "bold_captions" in types
    assert "karaoke_yellow" in types
    assert "minimal" in types


@pytest.mark.asyncio
async def test_generate_srt_basic():
    service = SubtitleStylingService()
    subs = [
        {"start": 0.0, "end": 2.0, "text": "Hello world"},
        {"start": 2.5, "end": 5.0, "text": "This is a test"},
    ]
    path = service._generate_srt(subs, 0.0)
    assert path.endswith(".srt")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Hello world" in content
    assert "This is a test" in content


@pytest.mark.asyncio
async def test_srt_time_format():
    service = SubtitleStylingService()
    t = service._srt_time(125.5)
    assert t == "00:02:05,500"


@pytest.mark.asyncio
async def test_color_to_ass():
    service = SubtitleStylingService()
    # ASS alpha counts transparency: 00 is opaque, FF invisible.
    assert service._color_to_ass("#FFFFFF") == "00FFFFFF"
    assert service._color_to_ass("#00FFCC") == "00CCFF00"
    assert service._color_to_ass("#FF000080") == "7F0000FF"


def test_style_overrides_carry_the_editor_animation():
    from subtitle_styling.service import _style_overrides

    assert _style_overrides({"animation": "karaoke"})["animation"] == "karaoke"
    assert "animation" not in _style_overrides({"animation": "spin"})


def test_style_overrides_map_editor_config_onto_template_keys():
    from subtitle_styling.service import _style_overrides

    overrides = _style_overrides({
        "font_size": 30, "position_y": 75, "title_font_size": 500, "title_position_y": "12",
        "font_color": "#fff",
    })
    assert overrides == {
        "font_size": 30.0, "position_y": 0.75, "title_font_size": 96.0, "title_position_y": 0.12,
        "font_color": "#FFFFFF",
    }
    assert _style_overrides(None) == {}
