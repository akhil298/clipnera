"""Speech-to-text on Groq's hosted Whisper, for hosts without a GPU.

The audio is cut into compressed chunks small enough for the upload limit and
transcribed concurrently, then stitched back into one timeline. A few seconds of
overlap between chunks keeps a word that straddles a cut; the stitch keeps each
word once, from whichever chunk saw it first.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any

from groq import AsyncGroq

from core.config import get_settings
from core.logging_config import get_logger
from usage.recorder import record_llm_call

log = get_logger(__name__)

DEFAULT_MODEL = "whisper-large-v3-turbo"
# Ten minutes of 64 kbps mono MP3 is about 4.8 MB, far under the upload limit.
CHUNK_SECONDS = 600.0
OVERLAP_SECONDS = 2.0
MAX_PARALLEL_REQUESTS = 4
# A new segment starts after a pause this long, or once a segment is this many words.
SEGMENT_PAUSE_SECONDS = 0.8
MAX_SEGMENT_WORDS = 40


class GroqWhisperTranscriber:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or (getattr(settings, "GROQ_WHISPER_MODEL", "") or DEFAULT_MODEL)
        self._client = AsyncGroq(api_key=(getattr(settings, "GROQ_API_KEY", "") or "").strip(), timeout=300.0)

    @staticmethod
    def available() -> bool:
        return bool((getattr(get_settings(), "GROQ_API_KEY", "") or "").strip())

    async def transcribe(
        self, audio_path: str, duration: float, language: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Segments (with word timings) for the whole file, and the detected language."""
        starts = chunk_starts(duration)
        semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
        with tempfile.TemporaryDirectory() as workdir:
            async def run(index: int, start: float) -> tuple[list[dict[str, Any]], str]:
                length = min(CHUNK_SECONDS + OVERLAP_SECONDS, duration - start)
                async with semaphore:
                    path = await _encode_chunk(audio_path, start, length, Path(workdir) / f"chunk{index}.mp3")
                    return await self._transcribe_chunk(path, start, length, language)

            results = await asyncio.gather(*(run(i, start) for i, start in enumerate(starts)))

        words: list[dict[str, Any]] = []
        for chunk_words, _ in results:
            covered = words[-1]["end"] if words else -1.0
            words.extend(w for w in chunk_words if w["start"] >= covered - 0.05)
        detected = next((lang for _, lang in results if lang), language or "en")
        return group_words(words), detected

    async def _transcribe_chunk(
        self, path: Path, offset: float, length: float, language: str | None,
    ) -> tuple[list[dict[str, Any]], str]:
        started = time.monotonic()
        response = await self._client.audio.transcriptions.create(
            model=self.model,
            file=(path.name, path.read_bytes()),
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language=language,
            temperature=0.0,
        )
        await record_llm_call(
            "groq", self.model, audio_seconds=length,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        data = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        words = [
            {
                "start": round(offset + float(w.get("start", 0.0)), 3),
                "end": round(offset + float(w.get("end", 0.0)), 3),
                "word": str(w.get("word", "")).strip(),
            }
            for w in data.get("words") or []
            if str(w.get("word", "")).strip()
        ]
        if not words:
            # Word timings missing: fall back to segment-level ones.
            words = [
                {
                    "start": round(offset + float(s.get("start", 0.0)), 3),
                    "end": round(offset + float(s.get("end", 0.0)), 3),
                    "word": str(s.get("text", "")).strip(),
                }
                for s in data.get("segments") or []
                if str(s.get("text", "")).strip()
            ]
        return words, str(data.get("language") or "")


def chunk_starts(duration: float) -> list[float]:
    if duration <= 0:
        return [0.0]
    starts, cursor = [], 0.0
    while cursor < duration:
        starts.append(cursor)
        cursor += CHUNK_SECONDS
    return starts


def group_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Segments in the shape the rest of the pipeline reads: start, end, text, words."""
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if current:
            segments.append({
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": " ".join(w["word"] for w in current),
                "confidence": 1.0,
                "speaker": None,
                "words": list(current),
            })
            current.clear()

    for word in words:
        if current:
            pause = word["start"] - current[-1]["end"]
            sentence_end = current[-1]["word"].endswith((".", "?", "!"))
            if pause >= SEGMENT_PAUSE_SECONDS or len(current) >= MAX_SEGMENT_WORDS or (sentence_end and len(current) >= 8):
                flush()
        current.append(word)
    flush()
    return segments


async def _encode_chunk(audio_path: str, start: float, length: float, out: Path) -> Path:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", audio_path,
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", str(out),
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"Could not encode audio chunk: {stderr.decode('utf-8', errors='ignore')[-200:]}")
    return out
