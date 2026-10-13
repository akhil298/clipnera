"""The finishing touches of a social short, added to a plan by rule instead of left to the model.

Asked for something "punchy" or "engaging", a small model still plans cut, tighten, captions
and stops. So when the request is for a polished short, the plan that was chosen gains the
steps an editor would add: every other shot held closer, the key numbers on screen as they
are said, and sounds on the cuts and the numbers. Callout text is lifted from the spoken
words, never written: a figure nobody said can't appear.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from brain.plan_ir import MAX_STEPS, MomentRef, PlanIR, PlanStep, PlanText
from understanding.mud import MUD, Word

_WANTS = re.compile(r"\b(punchy|engaging|viral|pro|professional|polished?|dynamic|hype|eye[- ]catching|scroll[- ]stopping|"
                    r"social|instagram|tiktok|reels?|shorts?)\b", re.I)
# Steps that re-cut the main track; the touches go after the last of them.
_CUTS = ("structure", "tighten", "beat_sync")
MAX_CALLOUTS = 3
# Words that never follow a number usefully ("18% in", "30 and").
_STOP = frozenset("a an and are as at but by for from in is it of on or our so than that the then to was we were with".split())
_NUMBER = re.compile(r"\d")


def wants_polish(prompt: str) -> bool:
    return bool(_WANTS.search(prompt))


def enrich(plan: PlanIR, muds: Mapping[str, MUD]) -> PlanIR | None:
    """``plan`` with the touches it lacks, or None when it builds no cut or already has them all."""
    kinds = [step.kind for step in plan.steps]
    if "structure" not in kinds:
        return None
    after = next(step.id for step in reversed(plan.steps) if step.kind in _CUTS)
    texts = list(plan.text)
    steps: list[PlanStep] = []

    def add(kind: str, intent: str, depends_on: str, **params: str) -> str:
        step_id = f"p{len(steps) + 1}"
        steps.append(PlanStep(id=step_id, kind=kind, intent=intent, depends_on=[depends_on], params=params))  # type: ignore[arg-type]
        return step_id

    if "zoom" not in kinds:
        add("zoom", "Hold every other shot closer", after, style="punch")
    callouts = next((step.id for step in plan.steps if step.kind == "callouts"), None)
    if callouts is None:
        found = _callouts(plan, muds)
        if found:
            texts += found
            callouts = add("callouts", f"Put {len(found)} key number{'' if len(found) == 1 else 's'} on screen", after)
    sounds_on = {str(step.params.get("on") or "cuts") for step in plan.steps if step.kind == "sfx"}
    if "cuts" not in sounds_on:
        add("sfx", "Whoosh on the cuts", after, on="cuts")
    if callouts and "callouts" not in sounds_on:
        add("sfx", "Pop on each number", callouts, on="callouts")
    if not steps or len(plan.steps) + len(steps) > MAX_STEPS:
        return None
    return plan.model_copy(update={"steps": [*plan.steps, *steps], "text": texts})


def _callouts(plan: PlanIR, muds: Mapping[str, MUD]) -> list[PlanText]:
    """The numbers said in the plan's moments, strongest moment first, as callouts anchored to their words."""
    found: list[PlanText] = []
    for ref in plan.moment_refs():
        mud = muds.get(ref.asset)
        words = _words_of(ref, mud) if mud else []
        phrase = _number_phrase(words)
        if phrase is None:
            continue
        text, first, last = phrase
        found.append(PlanText(kind="callout", content=text,
                              anchor=MomentRef(asset=ref.asset, words=[first, last])))
        if len(found) == MAX_CALLOUTS:
            break
    return found


def _words_of(ref: MomentRef, mud: MUD) -> list[Word]:
    if ref.words is not None:
        return mud.words[ref.words[0]:ref.words[1] + 1]
    moment = next((m for m in mud.moments if m.id == ref.moment), None)
    return [w for w in mud.words if moment and w.t0 >= moment.t0 - 0.05 and w.t1 <= moment.t1 + 0.05]


def _number_phrase(words: list[Word]) -> tuple[str, int, int] | None:
    """The last number said in ``words`` with the word it counts ("40,000 followers", "18%"), and its word range.

    The last one, because a line builds to its figure ("from 200 followers to 40,000").
    """
    for n in range(len(words) - 1, -1, -1):
        if not _NUMBER.search(words[n].text):
            continue
        start = end = n
        # Transcribers split "40,000" and "4.8" into pieces; a piece that opens with a digit or a mark joins on.
        while start > 0 and _NUMBER.search(words[start - 1].text) and not words[start].text[0].isdigit():
            start -= 1
        while end + 1 < len(words) and re.match(r"^[%,.]", words[end + 1].text):
            end += 1
        number = "".join(w.text for w in words[start:end + 1]).rstrip(".,!?")
        follower = _plain(words[end + 1]) if end + 1 < len(words) else ""
        if number.endswith("%"):
            return number, words[start].i, words[end].i
        if _is_unit(follower):
            return f"{number} {follower}", words[start].i, words[end + 1].i
        # "from 200 followers to 40,000": the unit was said after an earlier number.
        unit = next((_plain(words[k + 1]) for k in range(start - 1, -1, -1)
                     if _NUMBER.search(words[k].text) and _is_unit(_plain(words[k + 1]))), None)
        return (f"{number} {unit}" if unit else number), words[start].i, words[end].i
    return None


def _plain(word: Word) -> str:
    return word.text.strip(".,!?").lower()


def _is_unit(word: str) -> bool:
    return word.isalpha() and word not in _STOP
