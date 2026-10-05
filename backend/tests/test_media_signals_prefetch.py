"""Topic research uses the media signals the pipeline started during transcription."""

from __future__ import annotations

import asyncio

import pytest

import content_intelligence.service as ci

pytestmark = pytest.mark.asyncio


async def test_a_prefetched_result_is_used_without_reading_the_video_again(monkeypatch):
    async def never(*_):
        raise AssertionError("media signals were read twice")

    monkeypatch.setattr(ci, "media_signals", never)

    async def ready():
        return None, [{"start": 0.0, "end": 2.0, "shows": "a desk"}]

    task = asyncio.create_task(ready())
    audio, scenes = await ci.ContentIntelligenceService._signals(task, "v.mp4", 10.0)
    assert scenes[0]["shows"] == "a desk"


async def test_a_failed_prefetch_is_read_again_inline(monkeypatch):
    async def fresh(*_):
        return None, ["inline"]

    monkeypatch.setattr(ci, "media_signals", fresh)

    async def broken():
        raise RuntimeError("gemini down")

    task = asyncio.create_task(broken())
    assert (await ci.ContentIntelligenceService._signals(task, "v.mp4", 10.0))[1] == ["inline"]


async def test_without_a_prefetch_the_signals_are_read_now(monkeypatch):
    async def fresh(*_):
        return None, ["now"]

    monkeypatch.setattr(ci, "media_signals", fresh)
    assert (await ci.ContentIntelligenceService._signals(None, "v.mp4", 10.0))[1] == ["now"]
