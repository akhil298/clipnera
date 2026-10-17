"""A reference reel: the creator's example of the style they want, measured and described for the director.

Its pace comes from the same shot detection as the footage, its look from one
vision call on a contact sheet of evenly spaced frames. Nothing of it goes into
the reel.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from clip.youtube_service import YouTubeService
from clip.youtube_url import extract_youtube_video_id
from edit_engine import perception, vision
from edit_engine.director import parse

MAX_SECONDS = 180
ENERGIES = ("low", "medium", "high")
STYLE_PROMPT = (
    "These frames are from one short-form video, in order. Describe how it is edited, for an editor copying the "
    "style: the captions (size, colour, position, word by word or in lines), other on-screen text, colour grade, "
    'framing and zooms. JSON only: {"style": "one or two sentences", "energy": "low|medium|high"} /no_think'
)


def is_supported_link(url: str) -> bool:
    """Links we can fetch a reference from: YouTube videos and Shorts."""
    return extract_youtube_video_id(url) is not None


async def download(url: str, folder: Path) -> Path:
    return await YouTubeService().download_short(url, folder, MAX_SECONDS)


def _energy(seconds_per_shot: float) -> str:
    return "high" if seconds_per_shot < 1.5 else "medium" if seconds_per_shot < 3.5 else "low"


async def study(path: str) -> dict[str, Any]:
    """The reference's length, cut rate, energy and look in a sentence."""
    info = await perception.probe_media(path)
    if not info.has_video or info.duration <= 0:
        raise ValueError("the reference isn't a video we can read")
    if info.duration > MAX_SECONDS + 1:
        raise ValueError(f"the reference is over {MAX_SECONDS // 60} minutes")
    frames = await perception.sample_frames(path, info)
    shots = max(1, len(await asyncio.to_thread(perception.detect_shots, frames, info.duration)))
    pace = info.duration / shots
    step = max(1, len(frames) // vision.PER_SHEET)
    picks = [frame for _, frame in frames[::step]][:vision.PER_SHEET]
    described = parse(await vision.ask_sheet(vision.contact_sheet(picks), STYLE_PROMPT, 400)) if picks else {}
    return {
        "duration_s": round(info.duration, 1), "shots": shots, "seconds_per_shot": round(pace, 2),
        "energy": described.get("energy") if described.get("energy") in ENERGIES else _energy(pace),
        "style": " ".join(str(described.get("style") or "").split())[:400],
    }
