"""Read-only tools that let the editor agent look into the project's media (BLUEPRINT §2.11.3).

Every result carries times in seconds and, as ``src``, the matching source frames
at the project's fps, ready for a clip's ``src_in``/``src_out``. Text from the
media is fenced in «» like the LCV.

The context is the editor agent's (editor.agent_tools.EditorContext): anything
with ``service.media(user_id, project_id)``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.tools import AgentTool
from understanding.lcv import untrusted
from understanding.mud import MUD
from understanding.search import bm25, passages
from understanding.service import ProjectMedia


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchInput(_Input):
    query: str = Field(..., min_length=1, max_length=300, description="Words to look for in speech and shot captions.")
    asset_ids: list[str] | None = Field(None, description="Only these assets; all when omitted.")
    top_k: int = Field(8, ge=1, le=20)


class TranscriptInput(_Input):
    asset_id: str
    t0: float = Field(0.0, ge=0, description="Seconds into the asset.")
    t1: float | None = Field(None, ge=0, description="Seconds into the asset; the end when omitted.")
    with_fillers: bool = Field(False, description="Mark filler words with ~ so they can be cut.")


class MomentsInput(_Input):
    asset_ids: list[str] | None = None
    kinds: list[Literal["quote", "action_peak"]] | None = None
    top_k: int = Field(10, ge=1, le=40)


class SilencesInput(_Input):
    asset_id: str
    min_duration: float = Field(0.3, ge=0, description="Seconds; shorter gaps are left out.")
    kinds: list[Literal["pause", "dead_air"]] | None = None


class BeatsInput(_Input):
    asset_id: str
    t0: float = Field(0.0, ge=0)
    t1: float | None = Field(None, ge=0)
    kinds: list[Literal["beat", "downbeat", "drop"]] = Field(default_factory=lambda: ["downbeat", "drop"])


async def _media(context: Any) -> ProjectMedia:
    return await context.service.media(context.user_id, context.project_id)


def _span(media: ProjectMedia, t0: float, t1: float) -> dict[str, Any]:
    return {"t0": round(t0, 3), "t1": round(t1, 3), "src": [round(t0 * media.fps), round(t1 * media.fps)]}


async def media_search(context: Any, args: SearchInput) -> dict[str, Any]:
    media = await _media(context)
    hits = bm25(args.query, passages(media.muds, args.asset_ids), args.top_k)
    return {"hits": [
        {"asset": p.asset_id, "kind": p.kind, "ref": p.ref, **_span(media, p.t0, p.t1), "score": round(score, 2),
         "text": untrusted(p.text)}
        for score, p in hits
    ], "searched": sorted(a for a in media.muds if not args.asset_ids or a in args.asset_ids)}


async def get_transcript_range(context: Any, args: TranscriptInput) -> dict[str, Any]:
    media = await _media(context)
    mud = media.mud(args.asset_id)
    end = mud.duration if args.t1 is None else args.t1
    lines = []
    for u in (u for u in mud.utterances if u.t1 > args.t0 and u.t0 < end):
        words = mud.words[u.w0:u.w1 + 1]
        # A word index every 10 words, for cutting at an exact word.
        text = " ".join(
            (f"[w{w.i}] " if (w.i - u.w0) % 10 == 0 else "") + (f"~{w.text}" if args.with_fillers and w.filler else w.text)
            for w in words
        )
        lines.append({"id": u.id, **_span(media, u.t0, u.t1), "text": untrusted(text)})
    return {"asset": args.asset_id, "utterances": lines}


async def get_moments(context: Any, args: MomentsInput) -> dict[str, Any]:
    # Moments are picked when first asked for, not when the footage arrives.
    await context.service.ensure_moments(context.user_id, context.project_id)
    media = await _media(context)
    found = [
        (asset_id, m) for asset_id, mud in sorted(media.muds.items())
        if not args.asset_ids or asset_id in args.asset_ids
        for m in mud.moments if not args.kinds or m.kind in args.kinds
    ]
    best = sorted(found, key=lambda pair: (-pair[1].score, pair[0], pair[1].t0))[:args.top_k]
    return {"moments": [
        {"asset": asset_id, "id": m.id, "kind": m.kind, **_span(media, m.t0, m.t1), "score": m.score, "why": m.why,
         "shots": m.shot_ids, "text": _quote(media.muds[asset_id], m.t0, m.t1)}
        for asset_id, m in best
    ]}


def _quote(mud: MUD, t0: float, t1: float) -> str | None:
    words = [w.text for w in mud.words if w.t0 >= t0 - 0.01 and w.t1 <= t1 + 0.01]
    return untrusted(" ".join(words[:30])) if words else None


async def get_silences(context: Any, args: SilencesInput) -> dict[str, Any]:
    media = await _media(context)
    mud = media.mud(args.asset_id)
    gaps = [s for s in mud.silences if s.t1 - s.t0 >= args.min_duration and (not args.kinds or s.kind in args.kinds)]
    return {"asset": args.asset_id, "total_seconds": round(sum(s.t1 - s.t0 for s in gaps), 2),
            "silences": [{"kind": s.kind, **_span(media, s.t0, s.t1)} for s in gaps]}


async def get_beats(context: Any, args: BeatsInput) -> dict[str, Any]:
    media = await _media(context)
    mud = media.mud(args.asset_id)
    end = mud.duration if args.t1 is None else args.t1
    within = [b for b in mud.beats if args.t0 <= b.t <= end]
    result: dict[str, Any] = {"asset": args.asset_id, "tempo_bpm": mud.music.tempo_bpm if mud.music else None}
    if "beat" in args.kinds:
        result["beats"] = [b.t for b in within]
    if "downbeat" in args.kinds:
        result["downbeats"] = [b.t for b in within if b.is_downbeat]
    if "drop" in args.kinds:
        drops = mud.music.drops if mud.music else []
        result["drops"] = [{"t": d.t, "strength": d.strength} for d in drops if args.t0 <= d.t <= end]
    if not mud.beats:
        result["note"] = "No beats: this asset wasn't analysed as music."
    return result


MEDIA_TOOLS = [
    AgentTool("media_search", "Find where something is said or shown in the project's footage. "
                              "Returns ranked moments with times and source frames.", SearchInput, media_search),
    AgentTool("get_transcript_range", "Read what is said in an asset between two times, with word indices "
                                      "for exact cuts.", TranscriptInput, get_transcript_range),
    AgentTool("get_moments", "The strongest moments in the project's footage: quotable lines and action peaks.",
              MomentsInput, get_moments),
    AgentTool("get_silences", "Pauses and dead air in an asset, for tightening speech.", SilencesInput, get_silences),
    AgentTool("get_beats", "Beats, bar downbeats and drops of a music asset, for cutting on the beat.",
              BeatsInput, get_beats),
]
