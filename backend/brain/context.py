"""EditContext: everything the director reads before it plans (BLUEPRINT §3B.1.2).

The media as moment digests (top 40 per asset, 6k tokens for all), the timeline with who
made each item, the last 30 changes as one line each, the selection and playhead, the
user's AI feature keys and their credits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from brain import style
from editor.history import human_owned, touched_of
from editor.model import EditorOp
from editor.service import EditorService
from editor.timeline import ClipItem, GraphicItem, MusicItem, SfxItem, TextItem, Timeline
from subscription.service import SubscriptionService
from understanding.lcv import tokens, untrusted
from understanding.mud import MUD
from understanding.service import ProjectMedia

MOMENTS_PER_ASSET = 40
DIGEST_BUDGET = 6_000
HISTORY_LINES = 30


@dataclass
class EditContext:
    project_id: str
    version: int
    timeline: Timeline
    media: ProjectMedia
    selection: list[str]
    playhead: int
    # Item id -> "user" (a person made or changed it) or "agent".
    by: dict[str, str]
    history: list[str]
    features: dict[str, Any]
    credits_left: int
    human_owned: set[str] = field(default_factory=set)
    # Learned taste (brain.style): resolved values and the director's style card.
    style: dict[str, Any] = field(default_factory=dict)
    style_card: str = ""

    @property
    def muds(self) -> dict[str, MUD]:
        return self.media.muds

    def render(self) -> str:
        """The context as the director's system block: digests, timeline, history, selection, keys."""
        return "\n\n".join([
            "<media>\n" + digests(self.media) + "\n</media>",
            "<timeline>\n" + timeline_summary(self.timeline, self.by) + "\n</timeline>",
            "<history>\n" + ("\n".join(self.history) or "no changes yet") + "\n</history>",
            f"<selection>{', '.join(self.selection) or 'nothing'} · playhead {self.playhead} "
            f"({self.playhead / self.timeline.fps:.2f}s)</selection>",
            "<entitlements>" + json.dumps(self.features, sort_keys=True) + f" credits_left={self.credits_left}</entitlements>",
            "<style_profile>\n" + (self.style_card or "No learned preferences yet.") + "\n(Explicit requests win; "
            "when you go against a preference, say so in plan.notes.)</style_profile>",
        ])


async def build_context(service: EditorService, user_id: str, project_id: str, *, selection: list[str],
                        playhead: int, session: Any) -> EditContext:
    project = await service.get(user_id, project_id)
    media = await service.media(user_id, project_id)
    rows = list((await session.execute(
        select(EditorOp).where(EditorOp.project_id == project_id).order_by(EditorOp.version)
    )).scalars().all())
    owned = human_owned(rows)
    by = {item: "agent" for row in rows if row.by_agent for item in touched_of(row)}
    by.update({item: "user" for item in owned})
    subscriptions = SubscriptionService.for_session(session)
    entitlements = await subscriptions.get_entitlements(user_id)
    beliefs = json.loads((await style.profile(session, user_id)).beliefs or "{}")
    return EditContext(
        project_id=project_id, version=project.version, timeline=project.timeline, media=media,
        selection=list(selection), playhead=playhead, by=by, history=history_lines(rows[-HISTORY_LINES:]),
        features={"ai.plan.candidates_k": entitlements.ai_plan_candidates_k,
                  "ai.critic.max_rounds": entitlements.ai_critic_max_rounds,
                  "ai.planner.model": entitlements.ai_planner_model},
        credits_left=await subscriptions.get_user_credit_balance(user_id), human_owned=set(owned),
        style=style.resolved(beliefs), style_card=style.style_card(beliefs),
    )


def digests(media: ProjectMedia, budget: int = DIGEST_BUDGET) -> str:
    """Each analysed asset with its top moments, trimmed evenly across assets to fit ``budget``."""
    blocks: dict[str, tuple[str, list[str]]] = {}
    for asset_id in sorted(media.names):
        mud = media.muds.get(asset_id)
        if mud is None:
            blocks[asset_id] = (f"{asset_id} {untrusted(media.names[asset_id])}: not analysed yet "
                                f"({media.statuses.get(asset_id, 'pending')})", [])
            continue
        # File names are the uploader's text: fenced like speech.
        head = (f"{asset_id} {untrusted(media.names[asset_id])}: {mud.kind} {mud.duration:.1f}s, speech {round(mud.speech_ratio * 100)}%"
                + (f", music {mud.music.tempo_bpm:.0f} bpm, drops {[d.t for d in mud.music.drops]}" if mud.music else "")
                + (f", {len(mud.shots)} shots, {len(mud.words)} words" if mud.kind == "video" else ""))
        moments = sorted(mud.moments, key=lambda m: -m.score)[:MOMENTS_PER_ASSET]
        lines = [f"  {m.id} {m.t0:.1f}-{m.t1:.1f}s {m.kind} {m.score:.2f} {_quote(mud, m.t0, m.t1)}" for m in
                 sorted(moments, key=lambda m: m.t0)]
        blocks[asset_id] = (head, lines)
    # Cut the lowest-scoring moments, the same share from every asset, until it fits.
    keep = 1.0
    while True:
        text = "\n".join(head + "".join("\n" + line for line in lines[:max(1, round(len(lines) * keep))] if lines)
                         for head, lines in blocks.values())
        if tokens(text) <= budget or keep < 0.05:
            return text or "no media yet"
        keep *= 0.8


def _quote(mud: MUD, t0: float, t1: float) -> str:
    words = [w.text for w in mud.words if w.t0 >= t0 - 0.01 and w.t1 <= t1 + 0.01]
    return untrusted(" ".join(words[:16])) if words else ""


def timeline_summary(timeline: Timeline, by: dict[str, str]) -> str:
    lines = [f"{timeline.duration} frames = {timeline.duration / timeline.fps:.1f}s at {timeline.fps} fps, "
             f"{timeline.width}x{timeline.height}, look {timeline.look}, "
             f"captions {'on' if timeline.captions and timeline.captions.enabled else 'off'}"]
    for track in timeline.tracks:
        lines.append(f"track {track.id} ({track.kind}{', muted' if track.muted else ''}{', hidden' if track.hidden else ''})")
        for item in track.items:
            lines.append(f"  {item.id} {item.at}-{item.end} by:{by.get(item.id, 'agent')} {_facts(item)}")
    return "\n".join(lines)


def _facts(item: Any) -> str:
    if isinstance(item, ClipItem):
        return f"clip {item.asset} src {item.src_in}-{item.src_out} speed {item.speed} vol {item.volume}"
    if isinstance(item, TextItem):
        return f"text {untrusted(item.text)} style {item.style} scale {item.transform.scale}"
    if isinstance(item, MusicItem):
        return f"music {item.track} {item.gain_db} dB"
    if isinstance(item, SfxItem):
        return f"sfx {item.name}"
    if isinstance(item, GraphicItem):
        return "solid flash" if item.extra.get("solid") else "graphic"
    return item.type


def history_lines(rows: list[EditorOp]) -> list[str]:
    """One line per change: version, who, what kind, which items and fields."""
    lines = []
    for row in rows:
        touched = touched_of(row)
        what = ", ".join(f"{item}({'/'.join(sorted(fields))})" for item, fields in sorted(touched.items())[:6])
        more = f" +{len(touched) - 6} more" if len(touched) > 6 else ""
        lines.append(f"v{row.version} {row.author} {row.kind}{' step ' + row.step_id if row.step_id else ''}: "
                     f"{what or 'project settings'}{more}")
    return lines
