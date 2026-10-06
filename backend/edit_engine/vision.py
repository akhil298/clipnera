"""What each shot shows, nine shots per vision call.

Shots' sharpest frames are tiled 3x3 into a numbered contact sheet, and one
call to a small vision model captions every tile. That is about a ninth of
the calls (and image tokens) of captioning frames one by one. Captioning is
perception, not judgement, so both plans use Groq's vision model.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import cv2
import numpy as np
from groq import AsyncGroq

from clients.ai.base import reply_text
from core.config import get_settings
from core.logging_config import get_logger
from reels.vision import FREE_MODEL
from usage.recorder import record_llm_call

log = get_logger(__name__)

TILE = 320
GRID = 3
PER_SHEET = GRID * GRID
MAX_SHEETS_FREE = 4
MAX_SHEETS_PRO = 10
PROMPT = (
    "This is a contact sheet of video shots, each tile numbered in its corner. For every tile, say what it shows "
    'in under 10 words, for a video editor. JSON only: {"tiles": [{"n": 1, "text": "..."}]} /no_think'
)


def _tile(frame: np.ndarray, label: int) -> np.ndarray:
    """The frame fitted into a square tile on black, with its number drawn in the corner."""
    height, width = frame.shape[:2]
    scale = TILE / max(height, width)
    resized = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
    tile = np.zeros((TILE, TILE, 3), np.uint8)
    y, x = (TILE - resized.shape[0]) // 2, (TILE - resized.shape[1]) // 2
    tile[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    cv2.rectangle(tile, (0, 0), (46, 34), (0, 0, 0), -1)
    cv2.putText(tile, str(label), (6, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    return tile


def contact_sheet(frames: list[np.ndarray], first_label: int = 1) -> bytes:
    """A JPEG of up to nine frames in a 3x3 grid, numbered from ``first_label``."""
    tiles = [_tile(frame, first_label + i) for i, frame in enumerate(frames[:PER_SHEET])]
    tiles += [np.zeros((TILE, TILE, 3), np.uint8)] * (PER_SHEET - len(tiles))
    rows = [np.hstack(tiles[r * GRID:(r + 1) * GRID]) for r in range(GRID)]
    ok, encoded = cv2.imencode(".jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise RuntimeError("Could not encode a contact sheet")
    return encoded.tobytes()


def parse_tiles(text: str) -> dict[int, str]:
    try:
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError:
        return {}
    tiles = data.get("tiles") if isinstance(data, dict) else None
    out: dict[int, str] = {}
    for tile in tiles if isinstance(tiles, list) else []:
        if isinstance(tile, dict) and isinstance(tile.get("n"), int):
            out[tile["n"]] = " ".join(str(tile.get("text") or "").split())[:80]
    return out


async def caption_sheet(sheet: bytes) -> dict[int, str]:
    """Tile number -> caption; an empty dict if the call fails."""
    settings = get_settings()
    started = time.monotonic()
    try:
        response = await AsyncGroq(api_key=settings.GROQ_API_KEY).chat.completions.create(
            model=FREE_MODEL, max_tokens=700, temperature=0.2, messages=[{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(sheet).decode()}"}},
            ]}],
        )
        usage = response.usage
        await record_llm_call("groq", FREE_MODEL, input_tokens=getattr(usage, "prompt_tokens", 0),
                              output_tokens=getattr(usage, "completion_tokens", 0),
                              latency_ms=int((time.monotonic() - started) * 1000),
                              response=reply_text(response))
        return parse_tiles(response.choices[0].message.content or "")
    except Exception as exc:
        log.warning("Contact sheet captioning failed: %s", exc)
        return {}


def shots_to_caption(shots: list[dict[str, Any]], is_pro: bool) -> list[int]:
    """Indices of the shots worth captioning within the plan's sheet budget: usable and longest first."""
    budget = (MAX_SHEETS_PRO if is_pro else MAX_SHEETS_FREE) * PER_SHEET
    ranked = sorted(range(len(shots)), key=lambda i: (not shots[i]["usable"], -(shots[i]["end"] - shots[i]["start"])))
    return sorted(ranked[:budget])


async def caption_shots(frames: list[np.ndarray]) -> list[str]:
    """One caption per frame, in order; blank where the model gave none."""
    firsts = range(0, len(frames), PER_SHEET)
    sheets = await asyncio.gather(*(caption_sheet(contact_sheet(frames[f:f + PER_SHEET])) for f in firsts))
    return [tiles.get(i + 1, "") for f, tiles in zip(firsts, sheets) for i in range(len(frames[f:f + PER_SHEET]))]
