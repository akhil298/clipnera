"""Ask or assume: the expected-cost rule for asking the user one question (BLUEPRINT §3B.1.4).

A question costs the user a round trip; a wrong guess costs a redo plus reading a wrong plan.
Ask only when guessing is the dearer of the two, there's a clear choice to offer as 2–4 chips,
nothing has been asked yet this turn, and it isn't about money.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from brain.intent import IntentFrame

# Seconds of the user's time.
REDO_SECONDS = 12.0
ATTENTION_SECONDS = 6.0
ASK_SECONDS = 8.0
ASK_PENALTY_SECONDS = 4.0
MIN_OPTIONS, MAX_OPTIONS = 2, 4
_MONEY = re.compile(r"\b(price|pricing plan|cost|credits?|pay|paid|upgrade|subscription|tier|plan level)\b", re.I)


@dataclass
class ClarifyDecision:
    ask: bool
    question: str | None = None
    options: list[str] = field(default_factory=list)
    # Seconds: the expected cost of guessing, and of asking.
    expected_cost: float = 0.0
    ask_cost: float = 0.0


def decide_clarify(frame: IntentFrame, *, asked_this_turn: int = 0, asked_in_conversation: int = 0,
                   question: str | None = None) -> ClarifyDecision:
    readings = sorted(frame.interpretations, key=lambda i: -i.p)
    best = readings[0] if readings else None
    expected = sum(i.p * i.distance * (REDO_SECONDS + ATTENTION_SECONDS) for i in readings[1:])
    ask_cost = ASK_SECONDS + ASK_PENALTY_SECONDS * asked_in_conversation
    options = [i.option or i.summary[:40] for i in readings][:MAX_OPTIONS]
    text = question or (f"Did you mean: {best.summary}?" if best else None)
    allowed = (
        asked_this_turn == 0
        and len(options) >= MIN_OPTIONS
        and text is not None
        and not _MONEY.search(text)
        and not any(_MONEY.search(option) for option in options)
    )
    if allowed and expected > ask_cost:
        return ClarifyDecision(True, text, options, expected, ask_cost)
    return ClarifyDecision(False, None, [], expected, ask_cost)
