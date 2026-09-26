"""Voiceover for a reel: the creator's own recording, or synthesised speech.

Synthesis is optional. Groq's Orpheus voice speaks English (its terms must be
accepted once in the Groq console); OpenAI's speech model speaks many
languages including Hindi and Telugu. With neither configured, a reel without
an uploaded voiceover is captions-only, timed at reading speed.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Protocol

import httpx
from groq import AsyncGroq

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

# Speech engines take a limited input per request; long scripts go in sentence chunks.
MAX_CHARS_PER_REQUEST = 180
READING_WORDS_PER_SECOND = 2.6


class Synthesizer(Protocol):
    def speaks(self, language: str) -> bool: ...

    async def speak(self, text: str, voice: str | None) -> bytes: ...


class GroqOrpheus:
    model = "canopylabs/orpheus-v1-english"
    default_voice = "troy"

    def speaks(self, language: str) -> bool:
        return language == "en"

    async def speak(self, text: str, voice: str | None) -> bytes:
        response = await AsyncGroq(api_key=get_settings().GROQ_API_KEY).audio.speech.create(
            model=self.model, voice=voice or self.default_voice, input=text, response_format="wav",
        )
        return await response.read()


class OpenAISpeech:
    url = "https://api.openai.com/v1/audio/speech"
    default_voice = "alloy"

    def speaks(self, language: str) -> bool:
        return True

    async def speak(self, text: str, voice: str | None) -> bytes:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.url, headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"model": settings.OPENAI_TTS_MODEL, "voice": voice or self.default_voice, "input": text, "response_format": "wav"},
            )
            response.raise_for_status()
            return response.content


def synthesizer_for(language: str) -> Synthesizer | None:
    settings = get_settings()
    candidates: list[Synthesizer] = []
    if settings.TTS_PROVIDER == "groq" and settings.GROQ_API_KEY:
        candidates.append(GroqOrpheus())
    if settings.TTS_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        candidates.append(OpenAISpeech())
    return next((s for s in candidates if s.speaks(language)), None)


def chunks(script: str, limit: int = MAX_CHARS_PER_REQUEST) -> list[str]:
    """Sentence-sized pieces no longer than ``limit``, splitting long sentences at commas or spaces."""
    pieces: list[str] = []
    for sentence in re.split(r"(?<=[.!?।])\s+", script.strip()):
        while len(sentence) > limit:
            cut = max(sentence.rfind(",", 0, limit), sentence.rfind(" ", 0, limit))
            cut = cut if cut > 0 else limit
            pieces.append(sentence[:cut + 1].strip())
            sentence = sentence[cut + 1:].strip()
        if sentence:
            pieces.append(sentence)
    return pieces


async def synthesize(script: str, language: str, voice: str | None, out: Path) -> bool:
    """Write the script as speech to ``out`` (wav); False when no engine speaks the language."""
    engine = synthesizer_for(language)
    if engine is None:
        return False
    with tempfile.TemporaryDirectory() as workdir:
        parts = []
        for index, piece in enumerate(chunks(script)):
            path = Path(workdir) / f"{index:03d}.wav"
            path.write_bytes(await engine.speak(piece, voice))
            parts.append(path)
        listing = Path(workdir) / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-ar", "44100", "-ac", "1", str(out), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Could not join voiceover parts: {stderr.decode('utf-8', 'ignore')[-200:]}")
    return True


def reading_timings(script: str) -> list[dict]:
    """Word timings at a comfortable reading pace, for a reel without a voice."""
    words, t = [], 0.4
    for word in script.split():
        length = max(0.25, len(word) / 12 + 1 / READING_WORDS_PER_SECOND - 0.1)
        words.append({"start": round(t, 3), "end": round(t + length, 3), "word": word})
        t += length + (0.35 if word.endswith((".", "!", "?", "।")) else 0.05)
    return words
