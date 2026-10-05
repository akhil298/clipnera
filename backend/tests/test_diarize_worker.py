"""Diarization runs in a child process that the parent can stop."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

pytestmark = pytest.mark.asyncio

from transcription import diarize_worker


class _Settings:
    HF_TOKEN = "token"
    DIARIZATION_TIMEOUT_SECONDS = 1
    DIARIZATION_THREADS = 0


@pytest.fixture
def settings(monkeypatch):
    s = _Settings()
    monkeypatch.setattr(diarize_worker, "get_settings", lambda: s)
    return s


def _fake_child(monkeypatch, script: str):
    """Swap the child for a tiny Python script; argv[1] is still the output path."""
    real = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        out = args[4]
        return await real(sys.executable, "-c", script, out, **{k: v for k, v in kwargs.items() if k != "cwd"})

    monkeypatch.setattr(diarize_worker.asyncio, "create_subprocess_exec", spawn)


async def test_no_token_means_no_diarization(settings):
    settings.HF_TOKEN = ""
    assert await diarize_worker.diarize("missing.wav") == []


async def test_turns_come_back_from_the_child(settings, monkeypatch):
    turns = [{"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"}]
    _fake_child(monkeypatch, f"import sys, json; open(sys.argv[1], 'w').write({json.dumps(json.dumps(turns))})")
    assert await diarize_worker.diarize("a.wav") == turns


async def test_a_child_that_runs_too_long_is_stopped(settings, monkeypatch):
    _fake_child(monkeypatch, "import time; time.sleep(30)")
    started = asyncio.get_running_loop().time()
    assert await diarize_worker.diarize("a.wav") == []
    assert asyncio.get_running_loop().time() - started < 5


async def test_a_failed_child_gives_no_turns(settings, monkeypatch):
    _fake_child(monkeypatch, "raise SystemExit(3)")
    assert await diarize_worker.diarize("a.wav") == []
