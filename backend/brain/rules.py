"""The film-grammar rulebook (brain/rulebook/*.yaml) and the checks behind its rules (BLUEPRINT §3B.2).

Rules are data: id, severity (H hard, S soft, G generator default), parameters and the check
that tests them. Every H rule with a check runs on a dry-run Timeline before a plan is shown
and before each step is applied; a violation of one blocks the plan unless the user asked for
exactly that and the rule is ``overridable``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from brain.intent import is_solid
from editor.timeline import ClipItem, TextItem, Timeline
from understanding.mud import MUD

RULEBOOK = Path(__file__).parent / "rulebook"


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[A-Z]{2}-\d{2}$")
    title: str
    severity: Literal["H", "S", "G"]
    check: str
    params: dict[str, Any] = Field(default_factory=dict)
    penalty: float = Field(0.0, ge=0, le=1)
    overridable: bool = False
    when_asked: bool = False
    explain: str


@dataclass(frozen=True)
class Violation:
    rule: str
    message: str
    severity: str
    items: tuple[str, ...] = ()


@lru_cache
def rulebook() -> dict[str, Rule]:
    """Every rule by id; a malformed file fails loudly at load (9.1.8)."""
    rules: dict[str, Rule] = {}
    adapter = TypeAdapter(list[Rule])
    for path in sorted(RULEBOOK.glob("*.yaml")):
        if path.name == "weights.yaml":
            continue
        for rule in adapter.validate_python(yaml.safe_load(path.read_text(encoding="utf-8"))):
            if rule.id in rules:
                raise ValueError(f"Rule {rule.id} is defined twice ({path.name}).")
            if rule.check != "none" and rule.check not in CHECKS and rule.check not in SCORED_CHECKS:
                raise ValueError(f"Rule {rule.id} names an unknown check {rule.check!r}.")
            rules[rule.id] = rule
    return rules


@lru_cache
def weights() -> dict[str, dict[str, float]]:
    data = yaml.safe_load((RULEBOOK / "weights.yaml").read_text(encoding="utf-8"))
    for genre, table in data.items():
        if abs(sum(table.values()) - 1.0) > 1e-6:
            raise ValueError(f"Score weights for {genre} don't add up to 1.")
    return data


def aspect_class(timeline: Timeline) -> str:
    ratio = timeline.width / timeline.height
    return "vertical" if ratio < 0.9 else "wide" if ratio > 1.2 else "square"


def hard_violations(timeline: Timeline, muds: Mapping[str, MUD], *, overridden: set[str] = frozenset()) -> list[Violation]:
    """Every H rule the Timeline breaks, except stylistic ones the user asked to break."""
    found: list[Violation] = []
    for rule in rulebook().values():
        if rule.severity != "H" or rule.check not in CHECKS:
            continue
        if rule.overridable and rule.id in overridden:
            continue
        found += CHECKS[rule.check](rule, timeline, muds)
    return found


def soft_violations(timeline: Timeline, muds: Mapping[str, MUD], prefix: str) -> list[Violation]:
    return [v for rule in rulebook().values() if rule.severity == "S" and rule.id.startswith(prefix)
            and rule.check in CHECKS for v in CHECKS[rule.check](rule, timeline, muds)]


# ---------------------------------------------------------------------------- checks


def _visual_clips(timeline: Timeline) -> list[tuple[str, ClipItem]]:
    return [(t.id, i) for t in timeline.tracks if t.kind in ("video", "overlay") for i in t.items
            if isinstance(i, ClipItem)]


def _word_cut(rule: Rule, timeline: Timeline, muds: Mapping[str, MUD]) -> list[Violation]:
    """CT-06: no clip edge falls inside a spoken word (±20 ms)."""
    tolerance = float(rule.params.get("tolerance_s", 0.02))
    found = []
    for track in timeline.tracks:
        for item in track.items:
            if not isinstance(item, ClipItem) or (mud := muds.get(item.asset)) is None:
                continue
            for edge in (item.src_in / timeline.fps, item.src_out / timeline.fps):
                word = next((w for w in mud.words if w.t0 + tolerance < edge < w.t1 - tolerance), None)
                if word is not None:
                    found.append(Violation(rule.id, f"{item.id} cuts inside the word “{word.text}”.", rule.severity,
                                           (item.id,)))
                    break
    return found


def _min_shot(rule: Rule, timeline: Timeline, _: Mapping[str, MUD]) -> list[Violation]:
    """CT-07: shots are at least 8 frames, flash frames aside."""
    least = int(rule.params.get("frames", 8))
    return [Violation(rule.id, f"{item.id} is only {item.frames} frames long.", rule.severity, (item.id,))
            for _, item in _visual_clips(timeline) if item.frames < least and not is_solid(item)]


def _duplicate_source(rule: Rule, timeline: Timeline, _: Mapping[str, MUD]) -> list[Violation]:
    """CT-08: the same source footage doesn't play twice."""
    limit = round(float(rule.params.get("max_overlap_s", 0.3)) * timeline.fps)
    clips = sorted((i for _, i in _visual_clips(timeline)), key=lambda c: (c.asset, c.src_in))
    found = []
    for a, b in zip(clips, clips[1:]):
        if a.asset == b.asset and min(a.src_out, b.src_out) - b.src_in > limit:
            found.append(Violation(rule.id, f"{a.id} and {b.id} show the same footage.", rule.severity, (a.id, b.id)))
    return found


def _texts(timeline: Timeline) -> list[TextItem]:
    return [i for t in timeline.tracks for i in t.items if isinstance(i, TextItem)]


def _safe_area(rule: Rule, timeline: Timeline, _: Mapping[str, MUD]) -> list[Violation]:
    """TX-01: text sits inside the platform-safe box for the frame's shape."""
    box = rule.params[aspect_class(timeline)]
    return [Violation(rule.id, f"{t.id} is outside the safe area.", rule.severity, (t.id,)) for t in _texts(timeline)
            if not (box["x"][0] <= t.transform.x <= box["x"][1] and box["y"][0] <= t.transform.y <= box["y"][1])]


def _reading_speed(rule: Rule, timeline: Timeline, _: Mapping[str, MUD]) -> list[Violation]:
    """TX-04: a title stays up for at least max(0.8 s, words / 3)."""
    found = []
    for text in _texts(timeline):
        needed = max(float(rule.params["min_title_s"]), len(text.text.split()) / float(rule.params["words_per_second"]))
        if text.dur / timeline.fps + 1e-6 < needed:
            found.append(Violation(rule.id, f"{text.id} is on screen {text.dur / timeline.fps:.1f}s; it needs "
                                            f"{needed:.1f}s to read.", rule.severity, (text.id,)))
    return found


def _chars_per_line(rule: Rule, timeline: Timeline, _: Mapping[str, MUD]) -> list[Violation]:
    """TX-05: no line of a title is longer than the frame allows (two lines at most)."""
    limit = int(rule.params[aspect_class(timeline)])
    found = []
    for text in _texts(timeline):
        lines = text.text.split("\n")
        if len(lines) > 2 or any(len(line) > limit * 2 for line in lines):
            found.append(Violation(rule.id, f"{text.id} has too many characters for one line.", rule.severity, (text.id,)))
    return found


def _ending(rule: Rule, timeline: Timeline, muds: Mapping[str, MUD]) -> list[Violation]:
    """SA-06: the last shot doesn't stop in the middle of a sentence."""
    clips = sorted((i for _, i in _visual_clips(timeline)), key=lambda c: c.end)
    if not clips:
        return []
    last = clips[-1]
    mud = muds.get(last.asset)
    if mud is None:
        return []
    end = last.src_out / timeline.fps
    open_line = next((u for u in mud.utterances if u.t0 + 0.2 < end < u.t1 - 0.3), None)
    if open_line is None:
        return []
    return [Violation(rule.id, f"The edit ends mid-sentence in {last.id}.", rule.severity, (last.id,))]


def _true_peak(rule: Rule, timeline: Timeline, _: Mapping[str, MUD]) -> list[Violation]:
    """AU-03 (estimate before render): nothing is boosted enough to clip."""
    found = []
    for track in timeline.tracks:
        for item in track.items:
            if isinstance(item, ClipItem) and track.kind == "audio" and item.volume > 1.41:
                found.append(Violation(rule.id, f"{item.id} is boosted above +3 dB and may clip.", rule.severity, (item.id,)))
    return found


CHECKS: dict[str, Callable[[Rule, Timeline, Mapping[str, MUD]], list[Violation]]] = {
    "word_cut": _word_cut, "min_shot": _min_shot, "duplicate_source": _duplicate_source, "safe_area": _safe_area,
    "reading_speed": _reading_speed, "chars_per_line": _chars_per_line, "ending": _ending, "true_peak": _true_peak,
}
# Checks the scorer computes as components rather than as pass/fail (brain.score).
SCORED_CHECKS = {"hook", "title_alone_start", "arc", "payoff", "cta_end", "tutorial_order", "pacing", "jump_cut",
                 "transitions", "beat_alignment", "beat_error", "silence"}
