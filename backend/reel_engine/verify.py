"""Verify, before the render: the best hook of the director's options, and every label checked against its shot.

One vision call sees a 3-frame strip of each hook option and of each item that names something on screen
(picture labels, chapters, the title) and answers: which hook stops the scroll, and for each item whether it
matches what is visible right then - kept, rewritten for what is shown, or dropped. Words said aloud need no
check against the picture; spelling was fixed by the director.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.ai import vision_json
from reel_engine.director import DirectorPlan
from reel_engine.media import strip
from reel_engine.plan import Source, Word

log = get_logger(__name__)

CHECK_KINDS = {"two", "tag", "chapter", "keyword", "name"}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Check(_M):
    index: int
    verdict: Literal["keep", "rewrite", "drop"]
    lead: str
    text: str
    icon: str


class Verdicts(_M):
    best_hook: int
    hook_why: str
    subtitles: bool
    checks: list[Check]


SYSTEM = """You are the head editor checking a plan before it is rendered. HOOKS: strips of 3 frames from each hook
option; pick the one most likely to stop someone scrolling (a finished result, a strong face or reaction, motion,
a surprising moment), as its index. SUBTITLES: true only when the hook frames show subtitles burned into the picture
(a line of text near the bottom that changes with the speech); a diagram, sign or title is not subtitles. ITEMS: each item is a strip (start, middle, end) of ONE shot and the label
planned over it. keep it if it names what is clearly visible or happening in that shot; rewrite it (same kind,
lead 0-3 small words, text 1-2 words, icon = search words) for what IS shown; drop it if nothing there deserves a
label. A chapter opens a step: keep it when this shot shows that step starting. JSON only."""


async def verify(d: DirectorPlan, sources: list[Source], words: list[Word]) -> tuple[int, str, list[str]]:
    """Picks the hook and fixes the director's picture-anchored labels and sections in place; returns (hook, why, changes)."""
    paths = {s.index: s.path for s in sources}
    jpegs: list[bytes] = []
    lines: list[str] = []
    for n, hook in enumerate(d.hooks[:3]):
        c = hook.clip
        src, a, b = c.src, c.start, c.end
        if 0 <= c.w0 < len(words):
            src, a, b = words[c.w0].src, words[c.w0].t0, words[min(max(c.w1, c.w0), len(words) - 1)].t1
            said = " ".join(w.text for w in words[c.w0:min(c.w1, c.w0 + 30) + 1])
        else:
            said = ""
        if src in paths and a >= 0:
            jpegs.append(strip(paths[src], a, max(b, a + 0.5)))
            lines.append(f"hook {n}: {hook.why[:80]}{f' - says: {said}' if said else ''}")
    targets = []
    for beat in d.beats:
        if beat.kind in CHECK_KINDS and beat.w0 < 0 and beat.src in paths and beat.at >= 0:
            targets.append(("beat", beat, beat.src, beat.at, max(beat.until, beat.at + 0.8)))
    for n, sec in enumerate(d.sections):
        clip = next((c for c in d.story if c.section == n and c.src in paths and c.start >= 0), None)
        if clip:
            targets.append(("section", sec, clip.src, clip.start, clip.end))
    if not jpegs and not targets:
        return 0, "", []
    for k, (kind, item, src, a, b) in enumerate(targets):
        jpegs.append(strip(paths[src], a, b))
        label = f"chapter '{item.lead} {item.text}'" if kind == "section" else f"{item.kind} '{item.lead} {item.text}'"
        lines.append(f"item {k}: {label} icon '{item.icon}'")
    try:
        verdicts = await vision_json(SYSTEM, "Strips in order:\n" + "\n".join(lines) + "\n\nCheck them. JSON only.",
                                     [j for j in jpegs if j], Verdicts, max_tokens=4000)
    except Exception as exc:  # a check that cannot run keeps the director's plan as it is
        log.warning("Verify skipped: %s", exc)
        return 0, "", []
    changes = []
    drop = set()
    for check in verdicts.checks:
        if not 0 <= check.index < len(targets) or check.verdict == "keep":
            continue
        kind, item, *_ = targets[check.index]
        if check.verdict == "drop" and kind == "beat":
            drop.add(id(item))
            changes.append(f"dropped {item.kind} '{item.lead} {item.text}'")
        elif check.verdict == "rewrite" and check.text:
            changes.append(f"'{item.lead} {item.text}' -> '{check.lead} {check.text}'")
            item.lead, item.text = check.lead, check.text
            item.icon = check.icon or item.icon
            if kind == "section":
                item.short = check.text.split()[-1][:8].capitalize()
    d.beats = [b for b in d.beats if id(b) not in drop]
    if d.burned_captions and not verdicts.subtitles:
        # The footage shows no subtitles of its own: a reel is never shipped without captions.
        d.burned_captions = False
        d.caption_mode = "every_word" if d.caption_mode == "none" else d.caption_mode
        changes.append("captions kept: the footage has no burned-in subtitles")
    hook = min(max(0, verdicts.best_hook), max(0, len(d.hooks) - 1))
    log.info("Verify: hook %d, %d changes", hook, len(changes))
    return hook, verdicts.hook_why, changes
