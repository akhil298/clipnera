"""Cheap audio cues the model cannot hear from a transcript.

Loudness is measured on an 8 kHz mono decode of the source, so this reads only
the audio stream and costs seconds even for an hour of video. Energy is judged
against the surrounding minute rather than the whole file, so a quiet podcast
still has peaks and a loud one is not all peaks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np

from core.logging_config import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 8000
FRAME_SECONDS = 0.25
# Window, in seconds, that a frame's loudness is compared against.
CONTEXT_SECONDS = 60.0
# Standard deviations above the local mean that count as a peak.
PEAK_Z = 1.5


@dataclass
class AudioSignals:
    """Per-frame loudness z-scores; frame ``i`` covers ``[i * step, (i + 1) * step)``."""

    step: float
    z: np.ndarray

    def peak_between(self, start: float, end: float) -> float:
        """Highest loudness z-score within ``[start, end)``; 0 when out of range."""
        lo = max(0, int(start / self.step))
        hi = min(len(self.z), max(lo + 1, int(np.ceil(end / self.step))))
        return float(self.z[lo:hi].max()) if hi > lo else 0.0

    def peaks(self, limit: int = 300) -> list[list[float]]:
        """The loudest moments as ``[seconds, z]`` pairs, strongest first."""
        indices = np.where(self.z >= PEAK_Z)[0]
        ranked = indices[np.argsort(self.z[indices])[::-1]][:limit]
        return [[round(float(i * self.step), 2), round(float(self.z[i]), 2)] for i in sorted(ranked)]


async def extract_audio_signals(media_path: str) -> AudioSignals | None:
    """Loudness cues for a video or audio file; ``None`` if it has no readable audio."""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", media_path, "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1",
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        log.warning("Audio signal extraction failed: %s", stderr.decode("utf-8", errors="ignore")[-200:])
        return None
    return await asyncio.to_thread(loudness_signals, np.frombuffer(stdout, dtype=np.int16))


def loudness_signals(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> AudioSignals | None:
    frame = int(sample_rate * FRAME_SECONDS)
    count = len(samples) // frame
    if count < 8:
        return None
    frames = samples[: count * frame].astype(np.float64).reshape(count, frame)
    db = 10.0 * np.log10((frames ** 2).mean(axis=1) + 1.0)

    # Never wider than the audio itself, or the smoothing output outgrows it.
    window = max(3, min(count, int(CONTEXT_SECONDS / FRAME_SECONDS)))
    kernel = np.ones(window)
    # Divide by how many frames each window really holds, so the zero padding
    # at either end of the file does not read as silence and inflate the peaks.
    counts = np.convolve(np.ones(count), kernel, mode="same")
    mean = np.convolve(db, kernel, mode="same") / counts
    var = np.convolve((db - mean) ** 2, kernel, mode="same") / counts
    z = (db - mean) / np.sqrt(np.maximum(var, 1.0))
    return AudioSignals(step=FRAME_SECONDS, z=z)
