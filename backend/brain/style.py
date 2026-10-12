"""Style memory: learn a user's taste from how they correct the AI (TODO Phase 15, BLUEPRINT §3B.8).

When a person changes an item the AI made within their last 20 changes, that's a preference:
the title they shrank, the music they turned down, the cut they lengthened, the look they
swapped. Each becomes a PreferenceEvent (key, from, to, strength) and updates a belief with
forgetting (0.98 a day). Beliefs with confidence ≥ 0.4 shape plans: as a ≤ 300-token style card
for the director and as defaults the compiler uses. Explicit requests always win.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brain.model import StyleEvent, StyleProfile
from editor.history import touched_of
from editor.model import EditorOp
from editor.ops import SetCaptions, SetProject, TrimItem, UpdateItem
from editor.timeline import ClipItem, TextItem, Timeline

RECENT_TX = 20
FORGET_PER_DAY = 0.98
MAX_N = 30.0
USE_CONFIDENCE = 0.4
STICKY_CONFIDENCE = 0.7
CARD_TOKENS = 300
CORRECTION_STRENGTH = 1.0

LABELS = {
    "text.scale": ("Titles", lambda v: f"about {v:.2f}× the default size"),
    "music.gain_db": ("Music", lambda v: f"around {v:.0f} dB"),
    "pacing.shot_seconds": ("Shots", lambda v: f"around {v:.1f} s each"),
    "color.look": ("Look", lambda v: f"prefers {v}"),
    "captions.style": ("Captions", lambda v: f"style {v}"),
}


@dataclass(frozen=True)
class PreferenceEvent:
    key: str
    kind: str  # num | cat
    old: Any
    new: Any
    strength: float = CORRECTION_STRENGTH


def corrections(before: Timeline, after: Timeline, ops: Sequence[Any], agent_items: set[str],
                agent_changed_look: bool, agent_changed_captions: bool) -> list[PreferenceEvent]:
    """15.1.1–15.1.2: the preferences a human edit shows, when it corrects something the AI did."""
    events: list[PreferenceEvent] = []
    fps = before.fps
    for op in ops:
        item_id = getattr(op, "item", None)
        if isinstance(op, UpdateItem) and item_id in agent_items:
            old = _find(before, item_id)
            new = _find(after, item_id)
            if isinstance(old, TextItem) and isinstance(new, TextItem) and op.patch.transform and op.patch.transform.scale:
                events.append(PreferenceEvent("text.scale", "num", old.transform.scale, new.transform.scale))
            if isinstance(old, ClipItem) and isinstance(new, ClipItem) and op.patch.volume is not None \
                    and _is_music(before, item_id):
                events.append(PreferenceEvent("music.gain_db", "num", _db(old.volume), _db(new.volume)))
        if isinstance(op, TrimItem) and item_id in agent_items:
            old, new = _find(before, item_id), _find(after, item_id)
            if isinstance(old, ClipItem) and isinstance(new, ClipItem) and not _is_music(before, item_id):
                events.append(PreferenceEvent("pacing.shot_seconds", "num", old.frames / fps, new.frames / fps))
        if isinstance(op, SetProject) and op.look and agent_changed_look and op.look != before.look:
            events.append(PreferenceEvent("color.look", "cat", before.look, op.look))
        if isinstance(op, SetCaptions) and op.style and agent_changed_captions and before.captions \
                and op.style != before.captions.style:
            events.append(PreferenceEvent("captions.style", "cat", before.captions.style, op.style))
    return events


def _find(timeline: Timeline, item_id: str) -> Any:
    try:
        return timeline.find(item_id)[1]
    except Exception:
        return None


def _is_music(timeline: Timeline, item_id: str) -> bool:
    track, item = timeline.find(item_id)
    return track.kind == "audio" and isinstance(item, ClipItem) and timeline.assets[item.asset].kind == "audio"


def _db(volume: float) -> float:
    return 20 * math.log10(max(volume, 1e-3))


def update(beliefs: dict[str, Any], event: PreferenceEvent, now: datetime) -> dict[str, Any]:
    """15.1.4: the precision-weighted update with forgetting (§3B.8.2)."""
    belief = dict(beliefs.get(event.key) or {})
    days = (now - datetime.fromisoformat(belief["at"])).total_seconds() / 86400 if "at" in belief else 0.0
    decay = FORGET_PER_DAY ** max(0.0, days)
    s = event.strength
    if event.kind == "num":
        # Scale-like values learn in log space so ×2 and ×0.5 weigh the same.
        log_space = event.key == "text.scale"
        x = math.log(event.new) if log_space else float(event.new)
        n = min(float(belief.get("n", 0.0)), MAX_N) * decay
        mean = float(belief.get("mean", x))
        var = float(belief.get("var", 0.0))
        new_mean = (n * mean + s * x) / (n + s)
        new_var = (n * (var + (mean - new_mean) ** 2) + s * (x - new_mean) ** 2) / (n + s)
        belief.update(type="num", mean=new_mean, var=new_var, n=n + s, log=log_space)
    else:
        counts = {k: v * decay for k, v in (belief.get("counts") or {}).items()}
        counts[str(event.new)] = counts.get(str(event.new), 0.0) + s
        counts[str(event.old)] = max(0.0, counts.get(str(event.old), 0.0) - 0.5 * s)
        belief.update(type="cat", counts=counts, n=sum(counts.values()))
    belief["at"] = now.isoformat()
    return {**beliefs, event.key: belief}


def confidence(belief: dict[str, Any]) -> float:
    n = float(belief.get("n", 0.0))
    return n / (n + 3)


def value(belief: dict[str, Any]) -> Any:
    if belief.get("type") == "num":
        return math.exp(belief["mean"]) if belief.get("log") else belief["mean"]
    counts = belief.get("counts") or {}
    return max(counts, key=counts.get) if counts else None


def resolved(beliefs: dict[str, Any]) -> dict[str, Any]:
    """15.2.2: the beliefs confident enough to use, as plain values for the compiler."""
    # "About two strong corrections" (§3B.8.2): a second's worth of forgetting mustn't keep it out.
    return {key: value(b) for key, b in sorted(beliefs.items())
            if confidence(b) >= USE_CONFIDENCE - 1e-3 and value(b) is not None}


def style_card(beliefs: dict[str, Any]) -> str:
    """15.2.1: what the director reads about the user's taste, at most ~300 tokens."""
    lines = [f"{LABELS[k][0]}: {LABELS[k][1](v)} (confidence {confidence(beliefs[k]):.0%})"
             for k, v in resolved(beliefs).items() if k in LABELS]
    card = "\n".join(lines)
    return card[: CARD_TOKENS * 4] if card else "No learned preferences yet."


async def profile(session: AsyncSession, user_id: str) -> StyleProfile:
    row = await session.scalar(select(StyleProfile).where(StyleProfile.user_id == user_id))
    if row is None:
        row = StyleProfile(user_id=user_id, beliefs="{}", version=0)
        session.add(row)
        await session.flush()
    return row


async def learn(session: AsyncSession, user_id: str, project_id: str, before: Timeline, after: Timeline,
                ops: Sequence[Any]) -> int:
    """Record what a human edit says about the user's taste; returns how many preferences it showed."""
    rows = list((await session.execute(select(EditorOp).where(EditorOp.project_id == project_id)
                                       .order_by(EditorOp.version.desc()).limit(RECENT_TX))).scalars().all())
    agent_rows = [r for r in rows if r.by_agent]
    agent_items = {item for r in agent_rows for item in touched_of(r)}
    looked = any("set_project" in r.ops and '"look"' in r.ops for r in agent_rows)
    captioned = any("set_captions" in r.ops for r in agent_rows)
    events = corrections(before, after, ops, agent_items, looked, captioned)
    if not events:
        return 0
    row = await profile(session, user_id)
    beliefs = json.loads(row.beliefs or "{}")
    now = datetime.utcnow()
    for event in events:
        beliefs = update(beliefs, event, now)
        session.add(StyleEvent(user_id=user_id, project_id=project_id, event=json.dumps(event.__dict__)))
    row.beliefs = json.dumps(beliefs)
    row.version += 1
    await session.commit()
    return len(events)


async def forget(session: AsyncSession, user_id: str, key: str) -> None:
    row = await profile(session, user_id)
    beliefs = json.loads(row.beliefs or "{}")
    beliefs.pop(key, None)
    row.beliefs = json.dumps(beliefs)
    row.version += 1
    await session.commit()
