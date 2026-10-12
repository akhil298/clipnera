"""Relative words in a prompt as exact changes: "bigger" is ×1.25, "quieter" is −3 dB (TODO 5.4).

"much bigger" or "bigger, bigger" compounds the step, "a bit bigger" halves it, and an
explicit amount ("20% bigger", "6 dB louder") replaces the default. Floors and ceilings are
applied where the change lands (see brain.micro), so repeating a word can't push a value
out of range.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Prop = Literal["scale", "volume_db", "length", "speed", "look", "x", "y", "at_seconds"]


@dataclass(frozen=True)
class Modifier:
    prop: Prop
    # mul: multiply by value; add: add value; set: use value (a look name, or a mute).
    mode: Literal["mul", "add", "set"]
    value: float | str


# word pattern -> (prop, mode, default step)
_TABLE: list[tuple[str, Prop, str, float | str]] = [
    (r"bigger|larger|enlarge|zoom in|scale up", "scale", "mul", 1.25),
    (r"smaller|shrink|zoom out|scale down", "scale", "mul", 0.8),
    (r"louder|turn (?:it )?up|boost", "volume_db", "add", 3.0),
    (r"quieter|softer|turn (?:it )?down|lower the volume", "volume_db", "add", -3.0),
    (r"unmute", "volume_db", "set", 0.0),
    (r"\bmute\b|silence it", "volume_db", "set", "mute"),
    (r"shorter|trim (?:it )?down|cut (?:it )?down|tighter", "length", "mul", 0.6),
    (r"longer|extend|lengthen", "length", "mul", 1.4),
    (r"faster|speed (?:it )?up", "speed", "mul", 1.25),
    (r"slower|slow (?:it )?down", "speed", "mul", 0.8),
    (r"warmer|warm (?:it )?up", "look", "set", "warm_film"),
    (r"cooler|colder|cool (?:it )?down", "look", "set", "teal_orange"),
    (r"(?:move|shift|nudge) (?:it |this |that )?left|to the left", "x", "add", -0.05),
    (r"(?:move|shift|nudge) (?:it |this |that )?right|to the right", "x", "add", 0.05),
    (r"(?:move|shift|nudge) (?:it |this |that )?up|higher", "y", "add", -0.05),
    (r"(?:move|shift|nudge) (?:it |this |that )?down|lower(?! the volume)", "y", "add", 0.05),
    (r"earlier", "at_seconds", "add", -0.5),
    (r"later", "at_seconds", "add", 0.5),
]
_STRONG = re.compile(r"\b(much|way|a lot|lot|really|very|significantly|double)\b")
_WEAK = re.compile(r"\b(a bit|a little|slightly|bit|tad|touch)\b")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DB = re.compile(r"(\d+(?:\.\d+)?)\s*db\b")
_TIMES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:x|times)\b")
_SECONDS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)\b")


def parse(prompt: str) -> list[Modifier]:
    """Every change the prompt asks for, one per property, in table order."""
    text = prompt.lower()
    found: list[Modifier] = []
    seen: set[Prop] = set()
    for pattern, prop, mode, step in _TABLE:
        hits = re.findall(rf"\b(?:{pattern})", text)
        if not hits or prop in seen:
            continue
        seen.add(prop)
        found.append(_amount(text, prop, mode, step, repeats=len(hits)))
    return found


def _amount(text: str, prop: Prop, mode: str, step: float | str, repeats: int) -> Modifier:
    if isinstance(step, str) or mode == "set":
        return Modifier(prop, "set", step)
    sign = 1 if (mode == "mul" and step > 1) or (mode == "add" and step > 0) else -1
    if prop == "volume_db" and (m := _DB.search(text)):
        return Modifier(prop, "add", sign * float(m.group(1)))
    if mode == "mul" and (m := _TIMES.search(text)):
        times = float(m.group(1))
        return Modifier(prop, "mul", times if sign > 0 else 1 / times)
    if mode == "mul" and (m := _PERCENT.search(text)):
        share = float(m.group(1)) / 100
        return Modifier(prop, "mul", 1 + share if sign > 0 else max(0.01, 1 - share))
    if prop == "at_seconds" and (m := _SECONDS.search(text)):
        return Modifier(prop, "add", sign * float(m.group(1)))
    power = float(repeats) + (1 if _STRONG.search(text) else 0)
    if _WEAK.search(text):
        power = 0.5
    if mode == "mul":
        return Modifier(prop, "mul", round(float(step) ** power, 4))
    return Modifier(prop, "add", round(float(step) * power, 4))
