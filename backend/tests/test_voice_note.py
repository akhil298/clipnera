"""Voice notes: a short recording transcribed for the studio chat."""

from __future__ import annotations

import pytest

from brain import voice
from core.exceptions import CustomException


@pytest.mark.asyncio
async def test_a_voice_note_becomes_text(monkeypatch):
    seen = {}

    async def fake_speech(path: str, duration: float):
        seen["path"], seen["duration"] = path, duration
        # Segments as the transcribers return them: text, and words with timings.
        return [{"text": " Make it", "words": []}, {"text": "", "words": [{"word": " punchier", "start": 1, "end": 2}]}], "en"

    monkeypatch.setattr(voice, "speech", fake_speech)
    assert await voice.transcribe(b"audio", "audio/webm;codecs=opus", 2.5) == "Make it punchier"
    assert seen["path"].endswith(".webm") and seen["duration"] == 2.5


@pytest.mark.parametrize(("kind", "size", "seconds", "code"), [
    ("video/mp4", 10, 2, "VOICE_TYPE"),
    ("audio/webm", 10, 61, "VOICE_TOO_LONG"),
    ("audio/webm", voice.MAX_BYTES + 1, 2, "VOICE_TOO_LONG"),
    ("audio/wav", 0, 2, "VOICE_EMPTY"),
])
@pytest.mark.asyncio
async def test_voice_notes_are_checked(kind, size, seconds, code):
    with pytest.raises(CustomException) as exc:
        await voice.transcribe(b"x" * size, kind, seconds)
    assert exc.value.code == code
