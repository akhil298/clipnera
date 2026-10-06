"""The Gemini pass: video pieces in, a timeline of what each shows out.

The video is cut into pieces of ``CHUNK_SECONDS``, each re-encoded silent at
one frame per second and 360p (the transcript already covers the audio, and
Gemini samples video at one frame per second anyway). Pieces are described in
parallel and every call is costed against the run's budget. Any failure logs
and yields fewer notes, never a failed pipeline.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from core.config import get_settings
from core.logging_config import get_logger
from usage.context import LlmBudgetExceeded, check_budget, llm_scope
from usage.recorder import record_llm_call

log = get_logger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CHUNK_SECONDS = 120.0
# A tail shorter than this joins the piece before it.
MIN_CHUNK_SECONDS = 20.0
PARALLEL_CALLS = 4
PROXY_HEIGHT = 360
# Thinking tokens share this cap; 2048 cut busy two-minute pieces off mid-JSON.
MAX_OUTPUT_TOKENS = 8192
REQUEST_TIMEOUT_SECONDS = 120.0
MAX_SHOWS_CHARS = 100

PROMPT = """You are logging footage for a video editor. This is {length} of a longer video, sound removed; the speech is transcribed separately.
Describe what is on screen over time. Start a new entry whenever the picture meaningfully changes: a camera cut, someone moving, gesturing or reacting, an object held up or shown, text or graphics appearing. Otherwise start one at least every 10 seconds.
For each entry give from and to as MM:SS from the start of this piece, and shows: under 15 words on who or what is visible and what they are doing. Be literal; never guess what anyone says."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "moments": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"from": {"type": "STRING"}, "to": {"type": "STRING"}, "shows": {"type": "STRING"}},
                "required": ["from", "to", "shows"],
            },
        },
    },
    "required": ["moments"],
}


async def describe_video(video_path: str, duration: float) -> list[dict[str, Any]]:
    """``{"start", "end", "shows"}`` entries in source seconds, or [] when disabled or failed."""
    settings = get_settings()
    if not (settings.VISUAL_TIMELINE_ENABLED and settings.GEMINI_API_KEY) or duration <= 0:
        return []
    started = time.monotonic()
    limit = asyncio.Semaphore(PARALLEL_CALLS)

    async def one(start: float, length: float) -> list[dict[str, Any]]:
        async with limit:
            return await _describe_chunk(video_path, start, length)

    with llm_scope(step="visual_timeline"):
        results = await asyncio.gather(*(one(s, n) for s, n in chunks(duration)), return_exceptions=True)
    moments: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, BaseException):
            log.warning("Visual timeline piece failed: %s", result)
        else:
            moments.extend(result)
    log.info("Visual timeline: %d moment(s) over %.0fs of video in %.1fs",
             len(moments), duration, time.monotonic() - started)
    return sorted(moments, key=lambda m: m["start"])


def chunks(duration: float) -> list[tuple[float, float]]:
    """``(start, length)`` pieces covering ``duration``."""
    pieces: list[list[float]] = []
    start = 0.0
    while start < duration:
        length = min(CHUNK_SECONDS, duration - start)
        if pieces and length < MIN_CHUNK_SECONDS:
            pieces[-1][1] += length
        else:
            pieces.append([start, length])
        start += length
    return [(start, length) for start, length in pieces]


async def _describe_chunk(video_path: str, start: float, length: float) -> list[dict[str, Any]]:
    try:
        check_budget()
    except LlmBudgetExceeded as exc:
        log.info("Visual timeline piece at %.0fs skipped: %s", start, exc)
        return []
    with tempfile.TemporaryDirectory() as workdir:
        proxy = Path(workdir) / "piece.mp4"
        await _make_proxy(video_path, start, length, proxy)
        video = proxy.read_bytes()
    reply = await _call_gemini(video, length)
    return parse_moments(reply, start, length)


async def _make_proxy(video_path: str, start: float, length: float, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", video_path,
        "-an", "-vf", f"fps=1,scale=-2:{PROXY_HEIGHT}", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "30", "-pix_fmt", "yuv420p", str(out),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"proxy encode failed: {stderr.decode('utf-8', errors='ignore')[-200:]}")


async def _call_gemini(video: bytes, length: float) -> str:
    settings = get_settings()
    model = settings.VISUAL_TIMELINE_MODEL
    body = {
        "contents": [{"parts": [
            {"inlineData": {"mimeType": "video/mp4", "data": base64.b64encode(video).decode("ascii")}},
            {"text": PROMPT.format(length=_clock(length))},
        ]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "mediaResolution": settings.VISUAL_TIMELINE_MEDIA_RESOLUTION,
        },
    }
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            GEMINI_URL.format(model=model), headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=body,
        )
    response.raise_for_status()
    payload = response.json()
    usage = payload.get("usageMetadata") or {}
    await record_llm_call(
        "gemini", model,
        input_tokens=int(usage.get("promptTokenCount") or 0),
        # Thinking tokens bill as output.
        output_tokens=int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0),
        latency_ms=round((time.monotonic() - started) * 1000),
    )
    parts = ((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(str(part.get("text") or "") for part in parts)


def parse_moments(reply: str, offset: float, length: float) -> list[dict[str, Any]]:
    """The model's entries in source seconds, clamped to the piece; malformed ones dropped."""
    try:
        items = json.loads(reply).get("moments") or []
    except (json.JSONDecodeError, AttributeError):
        items = _complete_entries(reply)
        log.warning("Visual timeline reply was not JSON, kept %d complete entr(ies): %s",
                    len(items), reply[:200])
    moments = []
    for item in items:
        start, end = _seconds(item.get("from")), _seconds(item.get("to"))
        shows = " ".join(str(item.get("shows") or "").split())[:MAX_SHOWS_CHARS]
        if start is None or not shows:
            continue
        start = min(max(0.0, start), length)
        end = min(max(start, end if end is not None else start), length)
        moments.append({"start": round(offset + start, 2), "end": round(offset + max(end, start + 1.0), 2),
                        "shows": shows})
    return moments


def _complete_entries(reply: str) -> list[dict[str, Any]]:
    """The whole entry objects in a reply that was cut off before its JSON closed."""
    entries = []
    for match in re.finditer(r"\{[^{}]*\}", reply):
        try:
            entries.append(json.loads(match.group()))
        except json.JSONDecodeError:
            continue
    return entries


def _seconds(value: Any) -> float | None:
    """``"MM:SS"``, ``"H:MM:SS"`` or a number of seconds."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    if not re.fullmatch(r"\d+(:\d{1,2}){1,2}(\.\d+)?", text):
        return None
    total = 0.0
    for part in text.split(":"):
        total = total * 60 + float(part)
    return total


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
