"""Type kits: the look of a reel's text, picked from a catalogue so reels stop looking alike.

A kit (data/type_kits.json) is a complete type design: the caption font, the big word's font, the title font, their
case and weights, the colours, and how the big word is set off (a block, an outline, a glow, a gradient, a sticker...).
The director picks the kit that fits the content; code holds the pick to the editing style's kits and keeps it from
repeating a kit that a sibling reel (same video) or the creator's recent reels already use. The renderer draws any kit
from its variables (beats/renderer/kits.css), so a new kit is a catalogue entry, not code.
"""

from __future__ import annotations

import colorsys
import json
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np

CATALOG = Path(__file__).resolve().parent / "data" / "type_kits.json"
FALLBACK_ACCENT = "#ffb020"


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    return {k["id"]: k for k in json.loads(CATALOG.read_text())["kits"]}


def legible(kit: dict) -> bool:
    """Captions a phone viewer reads at a glance: a lead word of weight 600 or more, or outlined; never thin
    letter-spaced type (a serif-editorial reel's captions read as faint)."""
    treatment = kit.get("lead_treatment")
    return treatment != "spaced" and (kit["lead"]["weight"] >= 600 or treatment in ("stroke", "glow"))


def for_style(style: str) -> list[dict]:
    """The readable kits an editing style may use (every readable kit when the style names none)."""
    kits = [k for k in catalog().values() if style in k["styles"] and legible(k)]
    return kits or [k for k in catalog().values() if legible(k)]


def prompt() -> str:
    """The TYPE KITS section of the director's instructions."""
    rows = [f"- {k['id']} ({', '.join(k['styles'])}): {k['about']}" for k in catalog().values() if legible(k)]
    return ("TYPE KITS (type_kit: the look of every caption, label and title in the reel). Pick the kit whose feel fits this "
            "creator, the topic and the footage's colours, from the kits listed for your STYLE; vary it - the same few kits "
            "on every reel is exactly what to avoid.\n" + "\n".join(rows))


def choose(picked: str, style: str, avoid: set[str] | frozenset[str] = frozenset(), seed: str = "") -> str:
    """The kit for a reel: the director's pick when the style allows it and it is not taken, else another of the
    style's kits sharing its mood (then any free one), chosen by ``seed`` so the choice is stable for a reel."""
    allowed = for_style(style)
    names = [k["id"] for k in allowed]
    if picked in names and picked not in avoid:
        return picked
    free = [k for k in allowed if k["id"] not in avoid] or allowed
    moods = set(catalog().get(picked, {}).get("moods", []))
    near = [k for k in free if moods & set(k["moods"])] or free
    return near[zlib.crc32(seed.encode()) % len(near)]["id"]


def palette_accent(frames: list[np.ndarray]) -> str:
    """A bright accent taken from the footage's own colours: the most common strong hue, pushed vivid; amber when the
    footage has no colour to speak of (grey studio, black and white)."""
    import cv2

    hues = []
    for image in frames:
        hsv = cv2.cvtColor(cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV).reshape(-1, 3)
        strong = hsv[(hsv[:, 1] > 90) & (hsv[:, 2] > 70)]
        hues += strong[:, 0].tolist()
    if len(hues) < 40:
        return FALLBACK_ACCENT
    counts = np.bincount(np.array(hues) // 6, minlength=31)
    hue = (int(np.argmax(counts)) * 6 + 3) / 180
    r, g, b = colorsys.hsv_to_rgb(hue, 0.78, 1.0)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


CLASH_HUE = 0.09      # accents closer than this (share of the colour wheel) to the footage's own colour don't read on it


def _hsv(colour: str) -> tuple[float, float, float]:
    r, g, b = (int(colour[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


def readable(accent: str, alt: str, footage: str) -> str:
    """The accent, unless it is the footage's own colour (peach words on an orange robe): then the kit's second colour
    if that one stands apart, else white."""
    if not footage or footage == FALLBACK_ACCENT:  # no footage colour to clash with
        return accent

    def clash(colour: str) -> bool:
        h1, s1, _ = _hsv(colour)
        h2, _, _ = _hsv(footage)
        return s1 > 0.25 and min(abs(h1 - h2), 1 - abs(h1 - h2)) < CLASH_HUE

    if not clash(accent):
        return accent
    return alt if not clash(alt) and _hsv(alt)[1] > 0.25 else "#ffffff"


def spec(kit_id: str, role: str, footage_accent: str = "") -> dict:
    """What the renderer needs for one graphic: the kit's classes and variables for ``role`` ("text" for captions and
    labels, "title" for titles, chapters and the call to action, which take the kit's title font)."""
    kit = catalog().get(kit_id) or next(iter(catalog().values()))
    key = kit["title"] if role == "title" else kit["key"]
    accent = (footage_accent or FALLBACK_ACCENT) if kit["accent"] == "footage" else readable(kit["accent"], kit["alt"], footage_accent)
    return {
        "classes": f"treat-{kit['treatment']} lead-{kit['lead_treatment']}",
        "vars": {
            "--lead-font": f'"{kit["lead"]["font"]}"', "--lead-weight": str(kit["lead"]["weight"]), "--lead-case": kit["lead"]["case"],
            "--key-font": f'"{key["font"]}"', "--key-weight": str(key["weight"]), "--key-case": key["case"],
            "--accent": accent, "--alt": kit["alt"], "--ink": kit["ink"],
        },
    }


def fonts() -> set[str]:
    """Every font family the catalogue uses (the tests check each is declared for the renderer)."""
    return {kit[part]["font"] for kit in catalog().values() for part in ("lead", "key", "title")}
