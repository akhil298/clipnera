"""Voice notes for the studio chat: a short recording, transcribed like footage is (Groq, else on this machine)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.exceptions import CustomException
from understanding.build import speech

MAX_SECONDS = 60
MAX_BYTES = 5 * 1024 * 1024
VOICE_TYPES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mp4": ".m4a"}


def _check(content_type: str, size: int, seconds: float) -> str:
    suffix = VOICE_TYPES.get(content_type.split(";")[0].strip())
    if not suffix:
        raise CustomException(message="Send the voice note as WebM, Ogg, WAV or M4A audio.", code="VOICE_TYPE", status_code=415)
    if size > MAX_BYTES or seconds > MAX_SECONDS:
        raise CustomException(message=f"Keep voice notes under {MAX_SECONDS} seconds.", code="VOICE_TOO_LONG", status_code=413)
    if size == 0:
        raise CustomException(message="The voice note was empty.", code="VOICE_EMPTY", status_code=400)
    return suffix


async def transcribe(data: bytes, content_type: str, seconds: float) -> str:
    """What was said in a voice note."""
    suffix = _check(content_type, len(data), seconds)
    with tempfile.TemporaryDirectory(prefix="clipnera-voice-") as work:
        path = Path(work) / f"note{suffix}"
        path.write_bytes(data)
        segments, _ = await speech(str(path), max(seconds, 1.0))
    # Each segment has its text, and its words with timings; the text is enough here.
    parts = [str(s.get("text") or " ".join(str(w.get("word", "")) for w in s.get("words") or [])) for s in segments]
    return " ".join(" ".join(parts).split())
