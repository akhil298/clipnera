from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from broll import generation
from broll.generation import VeoClient, master_prompt, start_generation
from core.exceptions import CustomException


def test_master_prompt_is_vertical_and_clean():
    prompt = master_prompt("rain on a city window", "I love rainy mornings")
    assert "rain on a city window" in prompt and "9:16" in prompt
    assert "No text" in prompt and "no logos" in prompt and "rainy mornings" in prompt


def mock_veo(monkeypatch, finish_after=2, error=None):
    calls = {"polls": 0, "body": None}

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "k"
        if request.method == "POST":
            calls["body"] = json.loads(request.content)
            assert request.url.path.endswith("/models/veo-3.1-lite-generate-preview:predictLongRunning")
            return httpx.Response(200, json={"name": "models/veo/operations/op1"})
        if request.url.path.endswith("/operations/op1"):
            calls["polls"] += 1
            if calls["polls"] < finish_after:
                return httpx.Response(200, json={"name": "op1"})
            if error:
                return httpx.Response(200, json={"done": True, "error": {"message": error}})
            return httpx.Response(200, json={"done": True, "response": {"generateVideoResponse": {
                "generatedSamples": [{"video": {"uri": "https://generativelanguage.googleapis.com/v1beta/files/v1:download"}}]}}})
        if request.url.path.endswith(":download"):
            return httpx.Response(200, content=b"mp4-bytes")
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(generation.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(generation, "POLL_SECONDS", 0.0)
    return calls


@pytest.mark.asyncio
async def test_veo_generates_polls_and_downloads(monkeypatch, tmp_path):
    calls = mock_veo(monkeypatch)
    out = tmp_path / "v.mp4"
    await VeoClient("k", "veo-3.1-lite-generate-preview").generate("a beach", 8, "720p", out)
    assert out.read_bytes() == b"mp4-bytes" and calls["polls"] == 2
    assert calls["body"]["parameters"] == {"aspectRatio": "9:16", "resolution": "720p", "durationSeconds": 8}


@pytest.mark.asyncio
async def test_a_refused_prompt_raises(monkeypatch, tmp_path):
    mock_veo(monkeypatch, finish_after=1, error="blocked by safety filters")
    with pytest.raises(RuntimeError, match="safety"):
        await VeoClient("k", "veo-3.1-lite-generate-preview").generate("x", 8, "720p", tmp_path / "v.mp4")


class FakeSubscriptions:
    def __init__(self, pro, fail=False):
        self.pro, self.fail, self.deducted = pro, fail, []

    async def get_entitlements(self, user_id):
        return SimpleNamespace(pro_ai_provider=self.pro)

    async def consume_daily_quota(self, user_id, key):
        self.quota = key

    async def deduct_credits(self, **kwargs):
        if self.fail:
            raise ValueError("Insufficient credits")
        self.deducted.append(kwargs["amount"])


def patch_generation(monkeypatch, subs, key="k"):
    queued = []

    class Queue:
        async def enqueue(self, job):
            queued.append(job)

    monkeypatch.setattr(generation.SubscriptionService, "for_session", lambda session: subs)
    monkeypatch.setattr(generation, "get_queue", lambda: Queue())
    monkeypatch.setattr(generation, "get_settings", lambda: SimpleNamespace(GEMINI_API_KEY=key, VEO_SCENE_CREDITS=120))
    return queued


@pytest.mark.asyncio
async def test_free_users_are_refused(monkeypatch):
    queued = patch_generation(monkeypatch, FakeSubscriptions(pro=False))
    with pytest.raises(CustomException) as err:
        await start_generation(None, "u", "beach", "", {"type": "reel_scene", "id": "r", "index": 0})
    assert err.value.code == "PRO_REQUIRED" and not queued


@pytest.mark.asyncio
async def test_without_a_key_nothing_is_charged(monkeypatch):
    subs = FakeSubscriptions(pro=True)
    queued = patch_generation(monkeypatch, subs, key="")
    with pytest.raises(CustomException) as err:
        await start_generation(None, "u", "beach", "", {"type": "reel_scene", "id": "r", "index": 0})
    assert err.value.status_code == 503 and not subs.deducted and not queued


@pytest.mark.asyncio
async def test_pro_users_are_charged_then_queued(monkeypatch):
    subs = FakeSubscriptions(pro=True)
    queued = patch_generation(monkeypatch, subs)
    await start_generation(None, "u", "beach", "ctx", {"type": "reel_scene", "id": "r", "index": 2})
    assert subs.deducted == [120] and subs.quota == "ai_shots" and queued[0].kind == "broll.generate"
    assert queued[0].payload["credits"] == 120 and queued[0].payload["target"]["index"] == 2


@pytest.mark.asyncio
async def test_insufficient_credits_is_402(monkeypatch):
    queued = patch_generation(monkeypatch, FakeSubscriptions(pro=True, fail=True))
    with pytest.raises(CustomException) as err:
        await start_generation(None, "u", "beach", "", {"type": "reel_scene", "id": "r", "index": 0})
    assert err.value.status_code == 402 and not queued


def test_video_is_priced_per_second():
    from usage.pricing import video_cost

    assert video_cost("gemini", "veo-3.1-lite-generate-preview", "720p", 8) == pytest.approx(0.40)
    assert video_cost("gemini", "veo-3.1-fast-generate-preview", "1080p", 8) == pytest.approx(0.96)


@pytest.mark.asyncio
async def test_rate_limits_are_retried_then_raised(monkeypatch, tmp_path):
    attempts = []

    def handle(request):
        attempts.append(request.method)
        return httpx.Response(429, json={"error": {"message": "quota"}})

    real = httpx.AsyncClient
    monkeypatch.setattr(generation.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(generation, "RETRY_SECONDS", 0.0)
    with pytest.raises(httpx.HTTPStatusError):
        await VeoClient("k", "m").generate("x", 8, "720p", tmp_path / "v.mp4")
    assert attempts == ["POST"] * generation.START_ATTEMPTS
