"""A plan as an editor reads it: the edit part by part, with what is said there and what happens.

Built from the plan's compiled Timeline (what the plan would actually do), so the card shows
the cuts, closer shots, slow motion, titles, sounds, graphics, B-roll and music where they land.
"""

from __future__ import annotations

from collections.abc import Mapping

from brain.render_adapter import main_clips, main_track
from brain.schema import PlanOutlinePart
from editor.timeline import ClipItem, GraphicItem, SfxItem, TextItem, Timeline
from understanding.mud import MUD

# A part ends at the first cut after this long.
PART_SECONDS = 30.0
# Footage left out between two clips of the same video, more than this, counts as a cut.
CUT_SECONDS = 0.1
SAID_WORDS = 9
# A shorter sentence is a false start or a filler, not what the part is about.
MIN_SAID_WORDS = 3
# At most this many times listed for one kind of action in a part.
TIMES = 3


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _said(part: list[ClipItem], muds: Mapping[str, MUD], fps: int) -> str:
    """The first real sentence that starts in the part (a stray "I" or "So" skipped), its opening words quoted."""
    lines = []
    for clip in part:
        mud = muds.get(clip.asset)
        t0, t1 = clip.src_in / fps, clip.src_out / fps
        lines += [[w.text for w in mud.words[u.w0:u.w1 + 1]] for u in (mud.utterances if mud else []) if t0 - 0.05 <= u.t0 < t1]
    words = next((line for line in lines if len(line) >= MIN_SAID_WORDS), lines[0] if lines else [])
    if not words:
        return ""
    return "“" + " ".join(words[:SAID_WORDS]) + ("…" if len(words) > SAID_WORDS else "") + "”"


def _at(label: str, times: list[float]) -> str:
    shown = ", ".join(_clock(t) for t in times[:TIMES]) + (f" and {len(times) - TIMES} more" if len(times) > TIMES else "")
    return f"{label} at {shown}"


def _moves(clip: ClipItem) -> bool:
    return len({k.v for k in clip.keyframes.get("scale", [])}) > 1 or len({k.v for k in clip.keyframes.get("x", [])}) > 1


def _closer(clip: ClipItem) -> bool:
    scale = clip.keyframes.get("scale")
    return (max(k.v for k in scale) if scale else clip.transform.scale) > 1.01


def outline(timeline: Timeline, muds: Mapping[str, MUD]) -> list[PlanOutlinePart]:
    fps, clips = timeline.fps, main_clips(timeline)
    parts: list[list[ClipItem]] = []
    for clip in clips:
        if not parts or (parts[-1][-1].end - parts[-1][0].at) / fps >= PART_SECONDS:
            parts.append([])
        parts[-1].append(clip)
    main = main_track(timeline)
    others = [(track, item) for track in timeline.tracks if track is not main and not track.hidden for item in track.items]
    found = []
    for n, part in enumerate(parts):
        start, end = part[0].at / fps, part[-1].end / fps
        last = n == len(parts) - 1
        inside = [(track, item) for track, item in others if start <= item.at / fps < end or (last and item.at / fps >= end)]
        actions: list[str] = []
        removed = [b.src_in - a.src_out for a, b in zip(part, part[1:]) if a.asset == b.asset and b.src_in - a.src_out > CUT_SECONDS * fps]
        if removed:
            actions.append(f"{len(removed)} cut{'s' if len(removed) > 1 else ''} ({sum(removed) / fps:.0f} s of pauses, fillers and retakes out)")
        for label, test in (("Push-in", _moves), ("Closer shot", lambda c: _closer(c) and not _moves(c))):
            if times := [c.at / fps for c in part if test(c)]:
                actions.append(_at(label, times))
        for speed in sorted({c.speed for c in part if c.speed != 1}):
            actions.append(_at(f"{'Slow motion' if speed < 1 else 'Sped up'} ({speed:g}×)", [c.at / fps for c in part if c.speed == speed]))
        for _, item in inside:
            if isinstance(item, TextItem):
                actions.append(f"“{item.text}” on screen at {_clock(item.at / fps)}")
        kinds: dict[str, list[float]] = {}
        for track, item in inside:
            if isinstance(item, SfxItem):
                kinds.setdefault(f"{item.name.replace('_', ' ')} sound", []).append(item.at / fps)
            elif isinstance(item, GraphicItem):
                name = "Flash" if "solid" in item.extra else str(item.extra.get("graphic") or "Graphic").replace("_", " ").capitalize()
                kinds.setdefault(name, []).append(item.at / fps)
            elif isinstance(item, ClipItem) and timeline.assets[item.asset].kind == "audio":
                kinds.setdefault("Music in", []).append(item.at / fps)
            elif isinstance(item, ClipItem):
                kinds.setdefault("Picture-in-picture" if item.transform.scale < 1 else "B-roll", []).append(item.at / fps)
        actions += [_at(label, times) for label, times in kinds.items()]
        found.append(PlanOutlinePart(start=round(start, 2), end=round(end, 2), said=_said(part, muds, fps),
                                     actions=actions))
    return found
