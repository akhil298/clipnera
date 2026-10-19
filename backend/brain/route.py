"""The intent router: one cheap model call that decides what a prompt is and which path it takes
(BLUEPRINT §3.5.1).

It reads the prompt, the selection, the playhead and a one-paragraph digest of the project,
and returns a RouteDecision. It never edits and never answers. The schema is closed and
every field required, so OpenAI's strict mode and Claude's output format both enforce it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from clients.ai import call_with_fallback
from editor.timeline import ClipItem, MusicItem, TextItem, Timeline

ROUTER_PROMPT = (Path(__file__).parent / "prompts" / "router.md").read_text(encoding="utf-8")
ROUTER_MAX_TOKENS = 400

Intent = Literal["new_edit", "refine_edit", "undo", "redo", "direct_op", "question", "export_request",
                 "asset_search", "chitchat", "unsafe"]
PathName = Literal["plan", "micro", "answer", "deterministic", "refuse"]
Agent = Literal["cut", "audio", "text", "color", "transitions", "curator", "reframe", "brand"]
RefKind = Literal["clip", "title", "caption", "music", "effect", "transition", "step", "range", "selection", "unknown"]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Reference(_Closed):
    phrase: str
    kind: RefKind


class Constraints(_Closed):
    targetDurationSec: float | None
    aspect: Literal["16:9", "9:16", "1:1", "4:5"] | None
    mood: str | None
    mustKeep: list[str]


class RouteDecision(_Closed):
    intent: Intent
    path: PathName
    agents: list[Agent]
    references: list[Reference]
    constraints: Constraints
    complexity: Literal[1, 2, 3, 4, 5]
    clarify: str | None
    safety: Literal["ok", "borderline", "block"]
    preference: str | None


def digest(timeline: Timeline, selection: Sequence[str], playhead: int, span: tuple[int, int] | None = None) -> str:
    """The project in one paragraph: what the router needs to tell a tweak from a new edit.

    ``span`` is a selected stretch of the timeline (start and end frame) the request is about.
    """
    kinds: dict[str, int] = {}
    for track in timeline.tracks:
        kinds[track.kind] = kinds.get(track.kind, 0) + 1
    items = [(track, item) for track in timeline.tracks for item in track.items]
    clips = sum(1 for _, item in items if isinstance(item, ClipItem))
    titles = [item for _, item in items if isinstance(item, TextItem)]
    has_music = any(isinstance(item, MusicItem) or (track.kind == "audio" and isinstance(item, ClipItem))
                    for track, item in items)
    selected = [item for _, item in items if item.id in set(selection)]
    lines = [
        f"Project: {timeline.duration / timeline.fps:.1f}s at {timeline.fps} fps, {timeline.width}x{timeline.height}, "
        f"look {timeline.look}.",
        "Tracks: " + (", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items())) or "none") + ".",
        f"Items: {clips} clips, {len(titles)} titles, music {'yes' if has_music else 'no'}, "
        f"captions {'on' if timeline.captions and timeline.captions.enabled else 'off'}.",
        f"Playhead: {playhead / timeline.fps:.1f}s.",
        "Selection: " + (", ".join(_describe(item) for item in selected) or "nothing") + ".",
    ]
    if span:
        lines.append(f"Selected range: {span[0] / timeline.fps:.1f}s to {span[1] / timeline.fps:.1f}s "
                     f"(frames {span[0]} to {span[1]}); \"this\" and \"here\" mean this range.")
    if titles:
        lines.append("Titles: <untrusted>" + " | ".join(t.text for t in titles[:8]) + "</untrusted>")
    return "\n".join(lines)


def _describe(item: object) -> str:
    kind = type(item).__name__.removesuffix("Item").lower()
    return f"{kind} {getattr(item, 'id', '')}"


async def route(prompt: str, timeline: Timeline, selection: Sequence[str], playhead: int,
                recent_turns: Sequence[str] = (), footage: str = "") -> RouteDecision:
    """Classify one prompt; falls over to the other provider if the router's is down.

    ``footage`` says what is in the project's files, so a new project isn't read as an empty one.
    """
    context = digest(timeline, selection, playhead)
    if footage:
        context += f"\n{footage}"
    if recent_turns:
        context += "\nLast turns:\n" + "\n".join(f"- {turn}" for turn in recent_turns[-3:])
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": f"{context}\n\nUser message:\n{prompt}"},
    ]
    return await call_with_fallback(
        "router", lambda client: client.chat_json(messages, RouteDecision, max_tokens=ROUTER_MAX_TOKENS),
    )
