"""The publisher worker runs inside the API: it starts with the app and stops with it."""

from __future__ import annotations

import asyncio
import base64

import pytest

import social.worker
from core import crypto
from core.config import get_settings

pytestmark = pytest.mark.asyncio


@pytest.fixture
def key_ring(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(get_settings(), "SOCIAL_TOKEN_ENCRYPTION_KEYS", value)
        monkeypatch.setattr(get_settings(), "SOCIAL_TOKEN_ACTIVE_KEY_VERSION", 1)
        crypto.get_token_cipher.cache_clear()

    yield _set
    crypto.get_token_cipher.cache_clear()


@pytest.fixture
def ticks(monkeypatch):
    count = []

    async def job() -> int:
        count.append(1)
        return 0

    monkeypatch.setattr(social.worker, "JOBS", (social.worker.Periodic("test", social.worker.timedelta(0), job),))
    monkeypatch.setattr(social.worker, "POLL_SECONDS", 0.01)
    return count


async def test_worker_runs_while_the_app_is_up_and_stops_on_shutdown(key_ring, ticks):
    key_ring("1:" + base64.b64encode(b"k" * 32).decode())
    async with social.worker.running_in_background():
        await asyncio.sleep(0.1)
        assert ticks
    seen = len(ticks)
    await asyncio.sleep(0.05)
    assert len(ticks) == seen


async def test_worker_does_not_start_without_an_encryption_key(key_ring, ticks):
    key_ring("")
    async with social.worker.running_in_background():
        await asyncio.sleep(0.05)
    assert ticks == []


async def test_a_stuck_job_is_cancelled_after_the_grace_period(key_ring, monkeypatch):
    key_ring("1:" + base64.b64encode(b"k" * 32).decode())
    cancelled = asyncio.Event()

    async def hangs() -> int:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return 0

    monkeypatch.setattr(social.worker, "JOBS", (social.worker.Periodic("hang", social.worker.timedelta(0), hangs),))
    monkeypatch.setattr(social.worker, "SHUTDOWN_GRACE_SECONDS", 0.05)
    async with social.worker.running_in_background():
        await asyncio.sleep(0.01)
    assert cancelled.is_set()
