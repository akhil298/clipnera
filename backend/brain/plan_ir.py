"""PlanIR: the director's plan, in symbols, not frames (BLUEPRINT §3B.1.5).

The model says which moments, in what order, in what style, and which steps; solvers
(brain.solvers) place every frame. So a plan may name moments, words and shots by id, but
never carry a time: a field that looks like one is rejected and the model is told to use ids.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from understanding.mud import MUD

SectionName = Literal["hook", "build", "payoff", "cta", "body", "outro"]
StepKind = Literal["structure", "tighten", "beat_sync", "music", "title", "captions", "look", "reframe", "flash"]
Strategy = Literal["chronological", "hook_first", "thematic", "music_led", "dialogue_led", "emotional_arc"]
Aspect = Literal["9:16", "1:1", "4:5", "16:9"]
MAX_STEPS = 12

# A params key that holds a time, e.g. "t0", "start", "at_sec", "frames".
_TIME_KEY = re.compile(r"(^|_)(t0|t1|start|end|at|time|times|sec|secs|seconds|ms|frame|frames|timestamp|tick|ticks)$")
ParamValue = str | float | int | bool | list[str]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MomentRef(_Closed):
    """One piece of footage, named by a MUD id: a moment, a word range or a shot."""

    asset: str
    moment: str | None = None
    # [first word index, last word index], from get_transcript_range.
    words: list[int] | None = Field(None, min_length=2, max_length=2)
    shot: str | None = None
    must_include: bool = False

    @model_validator(mode="after")
    def _one_kind(self) -> MomentRef:
        named = [self.moment is not None, self.words is not None, self.shot is not None]
        if sum(named) != 1:
            raise ValueError("A moment ref names exactly one of: moment, words, shot.")
        if self.words and self.words[0] > self.words[1]:
            raise ValueError("words is [first, last] with first <= last.")
        return self


class PlanSection(_Closed):
    section: SectionName
    moments: list[MomentRef] = Field(default_factory=list, max_length=60)
    energy: Literal["low", "mid", "high"] | None = None


class PlanText(_Closed):
    kind: Literal["title", "cta", "lower_third"]
    content: str = Field(..., min_length=1, max_length=80)
    # Over the opening, the closing, or a section of the structure.
    at: Literal["start", "end", "hook", "build", "payoff", "cta", "body", "outro"] = "start"


class PlanMusic(_Closed):
    # A music asset in the project (an audio asset analysed as music), or none to keep what's there.
    asset: str | None = None
    fit: Literal["exact", "loop", "none"] = "exact"
    align_drop_to: Literal["hook", "payoff"] | None = None
    gain_db: float | None = Field(None, ge=-60, le=12)


class PlanStyle(_Closed):
    pace: Literal["slow", "medium", "fast"] = "medium"
    look: str | None = None
    cut_on_beat: bool = False
    captions: bool = False
    caption_style: str | None = None
    # How tight speech gets: pauses longer than this style's gap are cut (brain.solvers.speech_tighten).
    tighten: Literal["none", "natural", "tight", "punchy"] = "none"


class PlanStep(_Closed):
    id: str = Field(..., min_length=1, max_length=20)
    kind: StepKind
    intent: str = Field(..., min_length=1, max_length=80)
    why: str = Field("", max_length=200)
    depends_on: list[str] = Field(default_factory=list)
    # Ids of IntentFrame asks this step satisfies.
    satisfies: list[str] = Field(default_factory=list)
    params: dict[str, ParamValue] = Field(default_factory=dict)
    optional: bool = False

    @field_validator("params")
    @classmethod
    def _no_times(cls, params: dict[str, ParamValue]) -> dict[str, ParamValue]:
        timed = sorted(key for key in params if _TIME_KEY.search(key.lower()))
        if timed:
            raise ValueError(f"Step params can't hold times ({', '.join(timed)}): name moments, words or shots "
                             "by id and the solvers place them.")
        return params


class PlanIR(_Closed):
    strategy: Strategy
    title: str = Field(..., min_length=1, max_length=60)
    summary: str = Field(..., min_length=1, max_length=240)
    # Constraints, not placements: the length to fit and the shape to output.
    target_seconds: float | None = Field(None, gt=0, le=3600)
    aspect: Aspect | None = None
    structure: list[PlanSection] = Field(default_factory=list, max_length=8)
    style: PlanStyle = Field(default_factory=PlanStyle)
    music: PlanMusic | None = None
    text: list[PlanText] = Field(default_factory=list, max_length=6)
    steps: list[PlanStep] = Field(..., min_length=1, max_length=MAX_STEPS)
    # How each explicit ask is met, in a line each, by ask id.
    constraints_echo: list[str] = Field(default_factory=list)
    # Items the user made that this plan may change, because the request names them.
    human_owned_ok: list[str] = Field(default_factory=list)
    notes: str = Field("", max_length=400)

    @model_validator(mode="after")
    def _steps_form_a_dag(self) -> PlanIR:
        seen: set[str] = set()
        for step in self.steps:
            if step.id in seen:
                raise ValueError(f"Two steps are called {step.id}.")
            later = [d for d in step.depends_on if d not in seen]
            if later:
                raise ValueError(f"Step {step.id} depends on {', '.join(later)}, which isn't an earlier step.")
            seen.add(step.id)
        return self

    def moment_refs(self) -> list[MomentRef]:
        return [ref for section in self.structure for ref in section.moments]


def ref_errors(plan: PlanIR, muds: Mapping[str, MUD]) -> list[str]:
    """Every moment, word range and shot the plan names that the media doesn't have, with the nearest real ids."""
    errors: list[str] = []
    for ref in plan.moment_refs():
        mud = muds.get(ref.asset)
        if mud is None:
            errors.append(f"There is no analysed asset {ref.asset}. Assets: {', '.join(sorted(muds)) or 'none'}.")
            continue
        if ref.moment is not None and ref.moment not in {m.id for m in mud.moments}:
            errors.append(_unknown("moment", ref.moment, ref.asset, [m.id for m in mud.moments]))
        if ref.shot is not None and ref.shot not in {s.id for s in mud.shots}:
            errors.append(_unknown("shot", ref.shot, ref.asset, [s.id for s in mud.shots]))
        # A last index past the end is read as "to the end" (brain.compile clamps it).
        if ref.words is not None and not 0 <= ref.words[0] < len(mud.words):
            errors.append(f"{ref.asset} has words 0-{len(mud.words) - 1}; {ref.words} is outside them.")
    if plan.music and plan.music.asset and plan.music.asset not in muds:
        errors.append(f"There is no analysed music asset {plan.music.asset}.")
    return errors


def _unknown(kind: str, wanted: str, asset: str, known: list[str]) -> str:
    near = difflib.get_close_matches(wanted, known, n=3, cutoff=0.0) if known else []
    hint = f" Nearest: {', '.join(near)}." if near else f" {asset} has no {kind}s."
    return f"{asset} has no {kind} {wanted}.{hint}"


def schema_for_tools() -> dict[str, Any]:
    return PlanIR.model_json_schema()
