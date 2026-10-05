"""Speech-to-text on Groq's hosted Whisper, for hosts without a GPU.

The audio is cut into compressed chunks small enough for the upload limit and
transcribed concurrently, then stitched back into one timeline. A few seconds of
overlap between chunks keeps a word that straddles a cut; the stitch keeps each
word once, from whichever chunk saw it first.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from groq import AsyncGroq

from core.config import get_settings
from core.logging_config import get_logger
from transcription.language import SENTENCE_TERMINALS, normalize_language, spoken_hindi_misread_as_urdu
from usage.recorder import record_llm_call

log = get_logger(__name__)

DEFAULT_MODEL = "whisper-large-v3"
# Ten minutes of 64 kbps mono MP3 is about 4.8 MB, far under the upload limit.
CHUNK_SECONDS = 600.0
OVERLAP_SECONDS = 2.0
MAX_PARALLEL_REQUESTS = 4
# A new segment starts after a pause this long, or once a segment is this many words.
SEGMENT_PAUSE_SECONDS = 0.8
MAX_SEGMENT_WORDS = 40
# Whisper treats its prompt as text already said, and on some audio it repeats
# the prompt instead of transcribing: a video titled "Program Your Brain for
# Success!" came back with that line in place of whole minutes of speech, half
# its words gone. A chunk showing the prompt this way is redone without it.
# Echoes are a run of this many of the prompt's words in order, or a phrase
# standing alone between pauses of ECHO_PAUSE_SECONDS made mostly of them.
ECHO_RUN_WORDS = 3
ECHO_PAUSE_SECONDS = 1.0
ECHO_PHRASE_WORDS = 6
ECHO_PHRASE_SHARE = 0.6


class GroqWhisperTranscriber:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or (getattr(settings, "GROQ_WHISPER_MODEL", "") or DEFAULT_MODEL)
        self._client = AsyncGroq(api_key=(getattr(settings, "GROQ_API_KEY", "") or "").strip(), timeout=300.0)

    @staticmethod
    def available() -> bool:
        return bool((getattr(get_settings(), "GROQ_API_KEY", "") or "").strip())

    async def transcribe(
        self, audio_path: str, duration: float, language: str | None = None, prompt: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Segments (with word timings) for the whole file, and the detected language."""
        starts = chunk_starts(duration)
        semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
        with tempfile.TemporaryDirectory() as workdir:
            async def run(index: int, start: float) -> tuple[list[dict[str, Any]], str]:
                length = min(CHUNK_SECONDS + OVERLAP_SECONDS, duration - start)
                async with semaphore:
                    path = await _encode_chunk(audio_path, start, length, Path(workdir) / f"chunk{index}.mp3")
                    words, detected = await self._transcribe_chunk(path, start, length, language, prompt)
                    if prompt and echoes_prompt(words, prompt):
                        plain, plain_language = await self._transcribe_chunk(path, start, length, language, None)
                        log.warning(
                            "Chunk %d echoed the transcription prompt (%d words); without it: %d words",
                            index, len(words), len(plain),
                        )
                        if len(plain) > len(words):
                            words, detected = plain, plain_language
                    if language is None and spoken_hindi_misread_as_urdu(detected):
                        log.info("Chunk %d detected as Urdu; re-transcribing as Hindi", index)
                        words, detected = await self._transcribe_chunk(path, start, length, "hi", prompt)
                    return words, detected

            results = await asyncio.gather(*(run(i, start) for i, start in enumerate(starts)))

        words: list[dict[str, Any]] = []
        for chunk_words, _ in results:
            covered = words[-1]["end"] if words else -1.0
            words.extend(w for w in chunk_words if w["start"] >= covered - 0.05)
        return group_words(words), dominant_language(results, language)

    async def _transcribe_chunk(
        self, path: Path, offset: float, length: float, language: str | None, prompt: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        started = time.monotonic()
        response = await self._client.audio.transcriptions.create(
            model=self.model,
            file=(path.name, path.read_bytes()),
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language=language,
            # Names and brands in the prompt are spelled the same way in the transcript.
            prompt=prompt or None,
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
        return words, normalize_language(str(data.get("language") or ""))


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t]


def echoes_prompt(words: list[dict[str, Any]], prompt: str) -> bool:
    """Whether a chunk's transcript repeats ``prompt`` rather than the speech."""
    vocabulary = _tokens(prompt)
    if not vocabulary:
        return False
    runs = {tuple(vocabulary[i:i + ECHO_RUN_WORDS]) for i in range(len(vocabulary) - ECHO_RUN_WORDS + 1)}
    tokens = [t for w in words for t in _tokens(w["word"])]
    if any(tuple(tokens[i:i + ECHO_RUN_WORDS]) in runs for i in range(len(tokens) - ECHO_RUN_WORDS + 1)):
        return True

    # Phrases are split at pauses, so each one stands alone.
    known = set(vocabulary)
    phrase: list[str] = []
    for index, word in enumerate(words):
        phrase.extend(_tokens(word["word"]))
        following = words[index + 1] if index + 1 < len(words) else None
        if following is None or following["start"] - word["end"] >= ECHO_PAUSE_SECONDS:
            if 2 <= len(phrase) <= ECHO_PHRASE_WORDS and sum(t in known for t in phrase) >= ECHO_PHRASE_SHARE * len(phrase):
                return True
            phrase = []
    return False


def dominant_language(results: list[tuple[list[dict[str, Any]], str]], requested: str | None) -> str:
    """The language most of the words were spoken in; chunks can differ in a mixed video."""
    counts: dict[str, int] = {}
    for words, code in results:
        if code:
            counts[code] = counts.get(code, 0) + len(words)
    return max(counts, key=counts.get) if counts else normalize_language(requested) or "en"


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
            sentence_end = current[-1]["word"].endswith(SENTENCE_TERMINALS)
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
