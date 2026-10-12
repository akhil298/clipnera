"""PlanIR → Timeline ops, one batch per plan step, through the solvers (BLUEPRINT §3B.1.6).

Deterministic: the same plan, Timeline and MUDs give byte-identical ops (ids come from step
ids, never random), so a plan can be scored, cached and replayed. Each step is compiled
against the Timeline the previous steps leave and dry-run with the Timeline's own rules
(editor.ops.apply_ops), so a step that can't apply is caught before the user approves.

The main video track is rebuilt as a list of source pieces: structure fills it, tighten
splits pieces at pauses, beat_sync moves the cuts between them; then it is laid out with no
gaps (the ripple close of 8.3.1). Repairs before execution (8.3) keep text in the safe area
and move any cut that lands inside a word to just after it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from brain.intent import event_frames
from brain.plan_ir import MomentRef, PlanIR, PlanStep
from brain.solvers import beat_snap, music_fit, reframe, speech_tighten, timing
from editor.ops import (
    AddItem,
    AddTrack,
    RemoveItem,
    SetCaptions,
    SetProject,
    UpdateItem,
    ItemPatch,
    apply_ops,
)
from editor.timeline import ClipItem, Keyframe, TextItem, Timeline, TimelineError, Track
from understanding.mud import MUD

ASPECT_SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}
TITLE_SECONDS = 3.0
FLASH_FRAMES = {24: 2, 25: 2, 30: 2, 50: 4, 60: 4}
# Text stays inside the platform-safe area: away from the top bar and the caption/UI band.
SAFE_X = (0.1, 0.9)
SAFE_Y = (0.12, 0.78)
WORD_END_PAD = 0.06
WORD_START_PAD = 0.09
MUSIC_TRACK, TITLE_TRACK, FLASH_TRACK = "ai_music", "ai_titles", "ai_flashes"
PACE_TARGET_SHOT = {"slow": 4.0, "medium": 2.5, "fast": 1.4}


class CompileError(Exception):
    """A step can't be turned into ops; ``step`` names it."""

    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step


@dataclass(frozen=True)
class Piece:
    asset: str
    src_in: int
    src_out: int
    ref: str = ""
    section: str = "body"


@dataclass
class CompiledStep:
    step_id: str
    kind: str
    intent: str
    ops: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class CompiledPlan:
    steps: list[CompiledStep]
    timeline: Timeline

    @property
    def ok(self) -> bool:
        return all(step.error is None for step in self.steps)

    @property
    def op_count(self) -> int:
        return sum(len(step.ops) for step in self.steps)

    def touched_items(self) -> set[str]:
        """Existing items the ops change or remove (by id)."""
        return {op.item for step in self.steps for op in step.ops if isinstance(getattr(op, "item", None), str)}


def compile_plan(plan: PlanIR, timeline: Timeline, muds: Mapping[str, MUD], *,
                 human_owned: set[str] = frozenset(), only: Sequence[str] | None = None,
                 style: Mapping[str, Any] | None = None) -> CompiledPlan:
    """Compile every step (or only the ids in ``only``), each against the Timeline the earlier ones leave.

    ``style`` is the user's learned taste (brain.style.resolved); it fills in only what the plan leaves open.
    """
    state = _State(plan, timeline, muds, human_owned, style or {})
    compiled: list[CompiledStep] = []
    for step in plan.steps:
        if only is not None and step.id not in only:
            continue
        out = CompiledStep(step.id, step.kind, step.intent)
        try:
            out.ops = state.compile(step, out.warnings)
            state.timeline = apply_ops(state.timeline, out.ops)  # 8.2.1: dry run with the Timeline's rules
        except (CompileError, TimelineError) as exc:
            out.ops = []
            out.error = str(exc) if isinstance(exc, CompileError) else f"{exc.code}: {exc.message}"
        compiled.append(out)
    return CompiledPlan(compiled, state.timeline)


class _State:
    def __init__(self, plan: PlanIR, timeline: Timeline, muds: Mapping[str, MUD], human_owned: set[str],
                 style: Mapping[str, Any]) -> None:
        self.plan = plan
        self.style = style
        self.timeline = timeline
        self.muds = muds
        self.owned = set(human_owned) - set(plan.human_owned_ok)
        self.fps = timeline.fps
        self.pieces: list[Piece] | None = None

    # ------------------------------------------------------------------ dispatch

    def compile(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        handler = getattr(self, f"_step_{step.kind}")
        return handler(step, warnings)

    def _id(self, step: PlanStep, n: int | str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "-", f"{step.id}-{n}")[:40]

    # ------------------------------------------------------------------ the main cut

    def _main(self) -> Track:
        main = next((t for t in self.timeline.tracks if t.kind == "video" and t.extra.get("role") == "main"), None)
        main = main or next((t for t in self.timeline.tracks if t.kind == "video"), None)
        if main is None:
            raise CompileError("structure", "The project has no video track.")
        return main

    def _current_pieces(self) -> list[Piece]:
        if self.pieces is None:
            self.pieces = [Piece(i.asset, i.src_in, i.src_out, i.id) for i in self._main().items
                           if isinstance(i, ClipItem)]
        return self.pieces

    def _relayout(self, step: PlanStep, pieces: list[Piece], warnings: list[str]) -> list[Any]:
        """Replace the main track's clips with ``pieces``, back to back from frame 0."""
        main = self._main()
        mine = [i for i in main.items if i.id in self.owned]
        if mine:
            raise CompileError(step.id, f"That would replace clips you made ({', '.join(i.id for i in mine)}). "
                                        "Name them in the request to let the AI change them.")
        pieces = _repair_word_edges(pieces, self.muds, self.fps)
        ops: list[Any] = [RemoveItem(op="remove_item", item=i.id) for i in main.items]
        at = 0
        for n, piece in enumerate(pieces):
            clip = ClipItem(type="clip", id=self._id(step, n), at=at, asset=piece.asset, src_in=piece.src_in,
                            src_out=piece.src_out)
            ops.append(AddItem(op="add_item", track=main.id, item=clip))
            at += clip.frames
        self.pieces = [Piece(p.asset, p.src_in, p.src_out, self._id(step, n), p.section) for n, p in enumerate(pieces)]
        if not pieces:
            warnings.append("No footage was placed.")
        return ops

    def _step_structure(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        candidates: list[timing.Candidate] = []
        sections: list[str] = []
        for section in self.plan.structure:
            for index, ref in enumerate(section.moments):
                span = self._span(ref)
                if span is None:
                    warnings.append(f"Skipped a moment of {ref.asset} that has no time.")
                    continue
                t0, t1, score = span
                candidates.append(timing.Candidate(ref.asset, t0, t1, score, ref.must_include,
                                                   hook=section.section == "hook" and index == 0, ref=_ref_name(ref)))
                sections.append(section.section)
        if not candidates:
            raise CompileError(step.id, "The plan names no moments to build the cut from.")
        if self.plan.target_seconds:
            result = timing.fit(candidates, dict(self.muds), self.plan.target_seconds, self.fps)
            warnings += result.warnings
            chosen = result.pieces
        else:
            chosen = [timing.variants(c, self.muds.get(c.asset))[0] for c in candidates]
        by_ref = dict(zip((c.ref for c in candidates), sections))
        pieces = [self._piece(v.asset, v.t0, v.t1, v.ref, by_ref.get(v.ref, "body")) for v in chosen]
        return self._relayout(step, [p for p in pieces if p.src_out > p.src_in], warnings)

    def _span(self, ref: MomentRef) -> tuple[float, float, float] | None:
        mud = self.muds.get(ref.asset)
        if mud is None:
            return None
        if ref.moment is not None:
            moment = next((m for m in mud.moments if m.id == ref.moment), None)
            return (moment.t0, moment.t1, moment.score) if moment else None
        if ref.shot is not None:
            shot = next((s for s in mud.shots if s.id == ref.shot), None)
            return (shot.t0, shot.t1, 0.5 if shot.usable else 0.2) if shot else None
        if ref.words is not None and ref.words[1] < len(mud.words):
            return mud.words[ref.words[0]].t0, mud.words[ref.words[1]].t1, 0.6
        return None

    def _piece(self, asset: str, t0: float, t1: float, ref: str = "", section: str = "body") -> Piece:
        frames = self.timeline.assets[asset].frames
        src_in = max(0, min(frames - 1, round(t0 * self.fps)))
        return Piece(asset, src_in, max(src_in + 1, min(frames, round(t1 * self.fps))), ref, section)

    def _step_tighten(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        style = str(step.params.get("style") or self.plan.style.tighten)
        style = "natural" if style == "none" else style
        out: list[Piece] = []
        for piece in self._current_pieces():
            mud = self.muds.get(piece.asset)
            if mud is None or not mud.words:
                out.append(piece)
                continue
            ranges = speech_tighten.keep_ranges(mud.words, piece.src_in / self.fps, piece.src_out / self.fps, style)
            out += [self._piece(piece.asset, a, b, piece.ref, piece.section) for a, b in ranges]
        removed = sum(p.src_out - p.src_in for p in self._current_pieces()) - sum(p.src_out - p.src_in for p in out)
        if removed <= 0:
            warnings.append("There were no pauses or filler words to cut.")
        return self._relayout(step, out, warnings)

    def _step_beat_sync(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        music = self._music_item()
        if music is None:
            raise CompileError(step.id, "There is no music on the timeline to cut to; add the music step first.")
        mud = self.muds.get(music.asset)
        if mud is None or not mud.beats:
            raise CompileError(step.id, "The music hasn't been analysed for beats yet.")
        beats = beat_snap.beats_on_timeline(
            [b.t for b in mud.beats], {b.t for b in mud.beats if b.is_downbeat},
            [d.t for d in mud.music.drops] if mud.music else [], fps=self.fps, music_at=music.at,
            music_src_in=music.src_in, speed=music.speed,
        )
        pieces = self._current_pieces()
        cuts, at = [], 0
        for piece in pieces[:-1]:
            at += piece.src_out - piece.src_in
            cuts.append(at)
        snapped = beat_snap.snap(cuts, beats)
        out, previous = [], 0
        for index, piece in enumerate(pieces):
            end = snapped[index] if index < len(snapped) else None
            if end is None:
                out.append(piece)
                continue
            length = end - previous
            frames = self.timeline.assets[piece.asset].frames
            out.append(Piece(piece.asset, piece.src_in, min(frames, piece.src_in + max(1, length)), piece.ref, piece.section))
            previous = end
        moved = sum(1 for a, b in zip(cuts, snapped) if a != b)
        warnings.append(f"{moved} of {len(cuts)} cuts moved onto beats.")
        return self._relayout(step, out, warnings)

    # ------------------------------------------------------------------ music, text, look, format, flashes

    def _music_item(self) -> ClipItem | None:
        for track in self.timeline.tracks:
            if track.kind == "audio":
                for item in track.items:
                    if isinstance(item, ClipItem) and (mud := self.muds.get(item.asset)) and mud.music:
                        return item
        return None

    def _track(self, track_id: str, kind: str, ops: list[Any]) -> Track:
        existing = next((t for t in self.timeline.tracks if t.id == track_id), None)
        if existing is None:
            ops.append(AddTrack(op="add_track", id=track_id, kind=kind))  # type: ignore[arg-type]
            return Track(id=track_id, kind=kind)  # type: ignore[arg-type]
        return existing

    def _step_music(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        music_plan = self.plan.music
        asset = (music_plan.asset if music_plan else None) or str(step.params.get("asset") or "") or None
        if asset is None:
            asset = next((a for a, m in sorted(self.muds.items()) if m.music is not None), None)
        if asset is None or asset not in self.timeline.assets:
            raise CompileError(step.id, "There is no music in the project to use. Upload a song first.")
        mud = self.muds.get(asset)
        if mud is None or mud.music is None:
            raise CompileError(step.id, f"{asset} hasn't been analysed as music yet.")
        ops: list[Any] = []
        track = self._track(MUSIC_TRACK, "audio", ops)
        ops += [RemoveItem(op="remove_item", item=i.id) for i in track.items if i.id not in self.owned]
        length = self.timeline.duration or round((self.plan.target_seconds or mud.duration) * self.fps)
        drop_at = None
        if music_plan and music_plan.align_drop_to and self.pieces:
            drop_at = self._section_start(music_plan.align_drop_to)
        biggest = max(mud.music.drops, key=lambda d: d.strength).t if mud.music.drops else None
        fitted = music_fit.fit([b.t for b in mud.beats if b.is_downbeat], mud.duration, length, self.fps,
                               drop=biggest, drop_at_frame=drop_at)
        gain = music_plan.gain_db if music_plan and music_plan.gain_db is not None else self.style.get("music.gain_db", -14.0)
        volume = 10 ** (float(gain) / 20)
        at = 0
        asset_frames = self.timeline.assets[asset].frames
        for n, segment in enumerate(fitted.segments):
            src_in = min(asset_frames - 1, round(segment.src_t0 * self.fps))
            src_out = min(asset_frames, max(src_in + 1, round(segment.src_t1 * self.fps)))
            clip = ClipItem(type="clip", id=self._id(step, n), at=at, asset=asset, src_in=src_in, src_out=src_out,
                            speed=fitted.speed, volume=round(min(2.0, volume), 4))
            ops.append(AddItem(op="add_item", track=track.id, item=clip))
            at += clip.frames
        if fitted.fade_out_frames:
            warnings.append("The song is faded out at the end to fit the length.")
        return ops

    def _section_start(self, section: str) -> int | None:
        at = 0
        for piece in self.pieces or []:
            if piece.section == section:
                return at
            at += piece.src_out - piece.src_in
        return None

    def _step_title(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        texts = [t for t in self.plan.text if step.params.get("kind") in (None, t.kind)] or self.plan.text
        content = str(step.params.get("content") or "")
        if content:
            texts = [t for t in texts if t.content == content] or texts
        if not texts:
            raise CompileError(step.id, "The plan has no text for this step.")
        ops: list[Any] = []
        track = self._track(TITLE_TRACK, "text", ops)
        # The AI's earlier titles give way; a person's stay.
        ops += [RemoveItem(op="remove_item", item=i.id) for i in track.items if i.id not in self.owned]
        total = self.timeline.duration
        length = min(round(TITLE_SECONDS * self.fps), max(1, total)) if total else round(TITLE_SECONDS * self.fps)
        for n, text in enumerate(texts):
            if text.at == "end":
                at = max(0, total - length)
            elif text.at == "start":
                at = 0
            else:
                at = self._section_start(text.at) or 0
            y = 0.72 if text.kind == "lower_third" else 0.3 if text.kind == "title" else 0.62
            item = TextItem(type="text", id=self._id(step, n), at=at, text=text.content, style=str(step.params.get("style") or text.kind),
                            dur=length)
            item.transform.y = y
            item.transform.scale = round(min(10.0, max(0.1, float(self.style.get("text.scale", 1.0)))), 4)
            ops.append(AddItem(op="add_item", track=track.id, item=_safe(item)))
        # Titles on one track can't overlap: keep only those that fit one after another.
        return _no_overlap(ops)

    def _step_captions(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        style = str(step.params.get("style") or self.plan.style.caption_style or "")
        change: dict[str, Any] = {"enabled": True, "follow": self._main().id}
        if style:
            change["style"] = style
        return [SetCaptions(op="set_captions", **change)]

    def _step_look(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        look = str(step.params.get("look") or self.plan.style.look or self.style.get("color.look") or "")
        if not look:
            raise CompileError(step.id, "Say which look to use.")
        return [SetProject(op="set_project", look=look)]

    def _step_reframe(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        aspect = str(step.params.get("aspect") or self.plan.aspect or "")
        ops: list[Any] = []
        if aspect in ASPECT_SIZES and (self.timeline.width, self.timeline.height) != ASPECT_SIZES[aspect]:
            width, height = ASPECT_SIZES[aspect]
            ops.append(SetProject(op="set_project", width=width, height=height))
        for item in self._main().items:
            if not isinstance(item, ClipItem) or item.id in self.owned:
                continue
            mud = self.muds.get(item.asset)
            if mud is None or not mud.shots:
                continue
            t0, t1 = item.src_in / self.fps, item.src_out / self.fps
            keys = reframe.path(reframe.samples_from_shots(mud.shots, t0, t1))
            frames = item.frames
            points = sorted({min(frames, max(0, round((t - t0) * self.fps / item.speed))): x for t, x in keys}.items())
            if len(points) < 2 or all(abs(x - 0.5) < 0.02 for _, x in points):
                continue
            keyframes = {"x": [Keyframe(f=f, v=round(x, 4)) for f, x in points]}
            ops.append(UpdateItem(op="update_item", item=item.id, patch=ItemPatch(keyframes=keyframes)))
        if not ops:
            warnings.append("Nothing needed reframing.")
        return ops

    def _step_flash(self, step: PlanStep, warnings: list[str]) -> list[Any]:
        events = str(step.params.get("events") or "drops")
        targets = event_frames(self.timeline, self.muds, events)
        if not targets:
            raise CompileError(step.id, f"The music on the timeline has no {events} to flash on.")
        ops: list[Any] = []
        track = self._track(FLASH_TRACK, "graphic", ops)
        ops += [RemoveItem(op="remove_item", item=i.id) for i in track.items if i.id not in self.owned]
        length = FLASH_FRAMES.get(self.fps, 2)
        colour = str(step.params.get("colour") or step.params.get("color") or "#FFFFFF")
        last = -length
        for n, frame in enumerate(targets):
            if frame < last + length or frame >= max(1, self.timeline.duration):
                continue
            item = {"type": "graphic", "id": self._id(step, n), "at": frame, "dur": length,
                    "extra": {"solid": colour}}
            ops.append(AddItem(op="add_item", track=track.id, item=item))  # type: ignore[arg-type]
            last = frame
        return ops


def _ref_name(ref: MomentRef) -> str:
    if ref.moment:
        return f"{ref.asset}:{ref.moment}"
    if ref.shot:
        return f"{ref.asset}:{ref.shot}"
    return f"{ref.asset}:w{ref.words[0]}-{ref.words[1]}" if ref.words else ref.asset


def _repair_word_edges(pieces: list[Piece], muds: Mapping[str, MUD], fps: int) -> list[Piece]:
    """8.3.3: an edge inside a word moves out of it (the end to just after, the start to just before)."""
    fixed = []
    for piece in pieces:
        mud = muds.get(piece.asset)
        if mud is None or not mud.words:
            fixed.append(piece)
            continue
        t0, t1 = piece.src_in / fps, piece.src_out / fps
        start_word = next((w for w in mud.words if w.t0 < t0 < w.t1), None)
        end_word = next((w for w in mud.words if w.t0 < t1 < w.t1), None)
        if start_word:
            t0 = max(0.0, start_word.t0 - WORD_START_PAD)
        if end_word:
            t1 = min(mud.duration, end_word.t1 + WORD_END_PAD)
        fixed.append(Piece(piece.asset, round(t0 * fps), max(round(t0 * fps) + 1, round(t1 * fps)), piece.ref, piece.section))
    return fixed


def _safe(item: TextItem) -> TextItem:
    """8.3.2: text outside the safe area moves to the nearest safe spot."""
    item.transform.x = min(SAFE_X[1], max(SAFE_X[0], item.transform.x))
    item.transform.y = min(SAFE_Y[1], max(SAFE_Y[0], item.transform.y))
    return item


def _no_overlap(ops: list[Any]) -> list[Any]:
    kept, end = [], -1
    for op in ops:
        if isinstance(op, AddItem) and isinstance(op.item, TextItem):
            if op.item.at < end:
                continue
            end = op.item.end
        kept.append(op)
    return kept
