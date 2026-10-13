"""Speech-to-text on this machine with faster-whisper, for when the hosted service can't be used.

Slower than the hosted model and it needs no key, so a dead key or an outage never leaves a
video without its words. Returns the same segments as ``GroqWhisperTranscriber.transcribe``.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from core.logging_config import get_logger
from transcription.language import normalize_language

log = get_logger(__name__)

# The size the upload pipeline's local path uses: accurate enough on a CPU without hours of work.
MODEL_SIZE = "small"


@lru_cache(maxsize=1)
def _model() -> Any:
    import faster_whisper

    return faster_whisper.WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def _transcribe(audio_path: str) -> tuple[list[dict[str, Any]], str]:
    # No voice-activity filter: it drops quiet speech, and every word matters for cutting.
    segments, info = _model().transcribe(audio_path, beam_size=5, vad_filter=False, word_timestamps=True)
    rows = [
        {"start": seg.start, "end": seg.end, "text": seg.text.strip(),
         "words": [{"start": w.start, "end": w.end, "word": w.word.strip(), "probability": round(w.probability, 3)}
                   for w in seg.words or [] if w.word.strip()]}
        for seg in segments
    ]
    return rows, normalize_language(info.language or "")


async def transcribe_local(audio_path: str) -> tuple[list[dict[str, Any]], str]:
    """Segments (with word timings) for the whole file, and the detected language."""
    log.info("Transcribing %s on this machine (%s)", audio_path, MODEL_SIZE)
    return await asyncio.to_thread(_transcribe, audio_path)
