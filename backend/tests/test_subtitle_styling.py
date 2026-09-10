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
    assert "karaoke" in types
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
    assert service._color_to_ass("#FFFFFF") == "FFFFFFFF"
    assert service._color_to_ass("#00FFCC") == "FFCCFF00"
