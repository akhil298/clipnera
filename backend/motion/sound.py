"""Sound effects for motion graphics: one sound per visual event, on its frame.

Sounds are the curated files in ``static/motion/sfx`` (see
``scripts/build_motion_sfx.py``). Each is placed so its peak lands on the
event: a pop on the frame a card appears, a click as each list item ticks, a
register as a money figure lands. A riser is placed so it ends on its event.
Levels sit well under the voice; the mix is limited so nothing clips.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from motion.graphics import COUNT_SECONDS, Placed
from motion.plan import BIG_NUMBER, CTA_CARD, ENTITY_TAG, LIST_CARD, REACTION

SFX_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "sfx"
SAMPLE_RATE = 48000
# dB applied to each (peak-normalised) sound: under the voice, never over it.
GAIN_DB = {
    "pop": -13.0, "click": -17.0, "soft_click": -15.0, "whoosh": -16.0, "whoosh_short": -15.0,
    "ding": -15.0, "cash": -14.0, "tick": -18.0, "boom": -12.0, "riser": -16.0,
}
# Sounds whose end, not their peak, lands on the event.
ENDS_ON_EVENT = frozenset({"riser"})
# Two sounds closer than this smear into one; the later is dropped.
MIN_SPACING = 0.12
MONEY = re.compile(r"[$₹€£¥]|\b(usd|inr|dollars?|rupees?|bucks)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Sound:
    """``name`` heard so that its peak (or end) falls at ``at`` seconds of the output."""

    name: str
    at: float


@lru_cache(maxsize=1)
def manifest() -> dict[str, dict]:
    path = SFX_DIR / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else {}


def sounds_for(cues: list[Placed]) -> list[Sound]:
    """The sounds the drawn ``cues`` make, spaced so none smear together."""
    sounds: list[Sound] = []
    for cue in cues:
        if cue.kind == LIST_CARD:
            sounds.append(Sound("whoosh_short", cue.start + 0.05))
            sounds += [Sound("click", max(cue.start, beat) + 0.03) for beat in cue.beats]
        elif cue.kind == BIG_NUMBER:
            sounds.append(Sound("tick", cue.start + 0.05))
            money = MONEY.search(f"{cue.data.get('value', '')} {cue.data.get('label', '')}")
            sounds.append(Sound("cash" if money else "ding", cue.start + COUNT_SECONDS))
        elif cue.kind == ENTITY_TAG:
            sounds.append(Sound("whoosh_short", cue.start + 0.05))
        elif cue.kind == CTA_CARD:
            sounds += [Sound("pop", cue.start + 0.03), Sound("ding", cue.start + 0.25)]
        elif cue.kind == REACTION:
            sounds.append(Sound("pop", cue.start + 0.02))
    spaced: list[Sound] = []
    for sound in sorted(sounds, key=lambda s: s.at):
        if sound.name in manifest() and (not spaced or sound.at - spaced[-1].at >= MIN_SPACING):
            spaced.append(sound)
    return spaced


def sound_path(name: str) -> str:
    return str(SFX_DIR / manifest()[name]["file"])


def onset(sound: Sound) -> float:
    """Output second the sound file must start at for its peak (or end) to land on ``sound.at``."""
    entry = manifest()[sound.name]
    lead = float(entry["seconds"]) if sound.name in ENDS_ON_EVENT else float(entry["peak"])
    return max(0.0, sound.at - lead)


def mix_graph(sounds: list[Sound], base: str, first_input: int, out: str = "a") -> list[str]:
    """Filter chains mixing ``sounds`` (inputs ``first_input``.. in order) onto audio ``base``, ending in ``[out]``."""
    chains = [f"[{base}]aresample={SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo[mbase]"]
    labels = ["[mbase]"]
    for index, sound in enumerate(sounds):
        delay = round(onset(sound) * 1000)
        chains.append(
            f"[{first_input + index}:a]aresample={SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={delay}|{delay},volume={GAIN_DB.get(sound.name, -15.0)}dB[m{index}]"
        )
        labels.append(f"[m{index}]")
    chains.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first:dropout_transition=0,"
        f"alimiter=limit=0.95:level=disabled[{out}]"
    )
    return chains
