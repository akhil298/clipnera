"""The never-do list (BLUEPRINT §3B.5.5, ND-01…ND-13), checked before every agent transaction.

Most items are guaranteed by construction elsewhere; this module checks the ones a single
transaction can break and names where the others are enforced, so the list stays honest:

ND-01 EditOps only — editor.service.apply is the only writer (always true here).
ND-02 no plan runs unapproved — brain.execute only runs approved plans; micro edits are P5.
ND-03 human-made items — editor.history.check_human_owned (HUMAN_OWNED).
ND-04 never empties the timeline or deletes source media — checked here (no op deletes assets).
ND-05/07/10 no new hard-rule failure (word cuts, mid-sentence ending, text outside safe area) — here.
ND-06 no unshown charge — brain.credits holds only the ceiling shown on the plan card.
ND-08 no side-effect changes to size the user set — here: only a plan's reframe step may resize.
ND-09 no invented text — here: an agent may add only text the plan (or the user) gave: its words must
      appear, in order, in one of the allowed sources (case and punctuation aside).
ND-11 no stale ops over human edits — editor.history.check_rebase (CONFLICT).
ND-12 bounded loops — brain.verify (MAX_ROUNDS) and the agent runtime's step limits.
ND-13 no hidden failures — every failed or skipped step keeps its reason on the plan card.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from brain.rules import hard_violations
from core.exceptions import CustomException
from editor.ops import AddItem, SetProject, UpdateItem
from editor.timeline import TextItem, Timeline
from understanding.mud import MUD

MAX_REPAIR_ROUNDS = 3


def _words(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.lower()))


def given(text: str, sources: frozenset[str]) -> bool:
    """Whether ``text`` comes from one of ``sources``: its words, in order, inside one of them."""
    words = _words(text)
    return bool(words) and any(f" {words} " in f" {_words(source)} " for source in sources)


class NeverDo(CustomException):
    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message=f"{rule}: {message}", code="NEVER_DO", status_code=422, extra={"rule": rule})


def check_agent_tx(before: Timeline, after: Timeline, ops: Sequence[Any], muds: Mapping[str, MUD], *,
                   allowed_text: frozenset[str] | None, may_resize: bool) -> None:
    if before.duration > 0 and after.duration == 0:
        raise NeverDo("ND-04", "That would leave the timeline empty.")
    new = {(v.rule, v.message) for v in hard_violations(after, muds)} - {(v.rule, v.message) for v in hard_violations(before, muds)}
    if new:
        rule, message = sorted(new)[0]
        raise NeverDo("ND-05", f"It would break {rule}: {message}")
    if not may_resize and any(isinstance(op, SetProject) and (op.width or op.height) for op in ops):
        raise NeverDo("ND-08", "Only a reframe step the user approved may change the frame size.")
    if allowed_text is not None:
        for op in ops:
            text = op.item.text if isinstance(op, AddItem) and isinstance(op.item, TextItem) else \
                op.patch.text if isinstance(op, UpdateItem) else None
            if text and not given(text, allowed_text):
                raise NeverDo("ND-09", f"“{text[:40]}” isn't text the user gave or approved.")
