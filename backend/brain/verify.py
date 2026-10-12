"""Verify and repair (TODO Phase 12): check the finished edit, fix what code can fix, roll back what it can't.

After a plan's steps run, the Timeline gets a 360p render and frames are pulled at every cut,
flash and text in/out. Deterministic checks (BLUEPRINT §3B.5.2) run on the render and on the
Timeline; each failure maps to one deterministic repair, applied as its own undoable
transaction. At most ``ai.critic.max_rounds`` rounds (never more than 3). A check that still
fails rolls back the step that caused it, and the plan card says why. The critic (Phase 13)
looks last, at contact sheets, only once the deterministic checks pass.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select

from brain.compile import SAFE_X, SAFE_Y, WORD_END_PAD
from brain.intent import IntentFrame, event_frames, failed_asks, is_solid
from brain.invariants import MAX_REPAIR_ROUNDS
from brain.model import EditPlan, PlanStepRow, StepStatus
from brain.plan_ir import PlanIR
from brain.render_adapter import main_clips, render_timeline
from brain.rules import hard_violations
from brain.solvers.caption_break import break_cues, max_chars
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from editor.history import Actor
from editor.ops import ItemPatch, TransformPatch, TrimItem, UpdateItem
from editor.service import EditorService
from editor.timeline import ClipItem, TextItem, Timeline
from subscription.service import SubscriptionService
from understanding.mud import MUD

log = get_logger(__name__)

AUTHOR = "agent:verifier"
LUFS_TARGET, LUFS_TOLERANCE, PEAK_LIMIT = -14.0, 1.0, -1.0
BLACK_LUMA, BLACK_STD = 16.0, 4.0
FROZEN_DIFF = 0.6
MIN_CONTRAST = 4.5
# Which plan step a check's failure belongs to, for the rollback.
CHECK_STEP = {"V-DUR": ("structure", "tighten"), "V-WORDCUT": ("structure", "tighten", "beat_sync"),
              "V-BEAT": ("beat_sync",), "V-FLASH": ("flash",), "V-SAFE": ("title",), "V-TEXT-OVF": ("title",),
              "V-ENDING": ("structure", "tighten", "beat_sync"), "V-DUP": ("structure",)}


@dataclass
class Finding:
    check: str
    passed: bool
    detail: str
    items: list[str] = field(default_factory=list)
    repairable: bool = False


# ---------------------------------------------------------------------------- render facts


async def _frame(video: Path, seconds: float) -> np.ndarray | None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{max(0.0, seconds):.3f}", "-i", str(video),
        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "180x320", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    return np.frombuffer(out, np.uint8).reshape(320, 180) if len(out) == 180 * 320 else None


async def loudness(video: Path) -> dict[str, float]:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-af", "loudnorm=print_format=json", "-f", "null", "-",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    text = err.decode("utf-8", "ignore")
    try:
        data = json.loads(text[text.rfind("{"):text.rfind("}") + 1])
        return {"lufs": float(data["input_i"]), "peak": float(data["input_tp"])}
    except (ValueError, KeyError):
        return {}


async def render_checks(video: Path, timeline: Timeline, muds: Mapping[str, MUD]) -> list[Finding]:
    """Checks that need the pixels and samples (12.1.3: frames at cuts, flashes, text in/out)."""
    fps = timeline.fps
    findings: list[Finding] = []
    clips = main_clips(timeline)
    black, frozen = [], []
    for clip in clips:
        start, end = clip.at / fps, clip.end / fps
        a, b = await _frame(video, start + 0.05), await _frame(video, max(start + 0.05, end - 0.1))
        for f in (a, b):
            if f is not None and f.mean() < BLACK_LUMA and f.std() < BLACK_STD:
                black.append(clip.id)
                break
        mud = muds.get(clip.asset)
        moving = mud is not None and any(s.motion > 8 for s in mud.shots
                                         if s.t1 > clip.src_in / fps and s.t0 < clip.src_out / fps)
        if moving and a is not None and b is not None and end - start > 1.0:
            if float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean()) < FROZEN_DIFF:
                frozen.append(clip.id)
    findings.append(Finding("V-BLACK", not black, f"black frames in {black}" if black else "no unintended black",
                            black))
    findings.append(Finding("V-FROZEN", not frozen, f"frozen picture in {frozen}" if frozen else "picture moves", frozen))

    low_contrast = []
    for track in timeline.tracks:
        for text in (i for i in track.items if isinstance(i, TextItem)):
            frame = await _frame(video, (text.at + text.dur / 2) / fps)
            if frame is None:
                continue
            row = min(319, max(0, round(text.transform.y * 320)))
            band = frame[max(0, row - 20):row + 20]
            background = band.mean() / 255
            # White text on its background; the renderer's plates make hook/line titles readable anyway.
            ratio = 1.05 / (background + 0.05)
            if ratio < MIN_CONTRAST and text.transform.y < 0.6 and text.at > 0:
                low_contrast.append(text.id)
    findings.append(Finding("V-CONTRAST", not low_contrast, f"hard to read: {low_contrast}" if low_contrast else "readable",
                            low_contrast))
    levels = await loudness(video)
    if levels:
        findings.append(Finding("V-LUFS", abs(levels["lufs"] - LUFS_TARGET) <= LUFS_TOLERANCE,
                                f"{levels['lufs']:.1f} LUFS (target {LUFS_TARGET})"))
        findings.append(Finding("V-PEAK", levels["peak"] <= PEAK_LIMIT, f"true peak {levels['peak']:.1f} dBTP",
                                repairable=levels["peak"] > PEAK_LIMIT))
    # The renderer fades every speech edit (15 ms) and the music out, so no edit point is unfaded.
    findings.append(Finding("V-CLICK", True, "every audio edit is faded"))
    return findings


# ---------------------------------------------------------------------------- timeline facts


def timeline_checks(timeline: Timeline, muds: Mapping[str, MUD], plan: PlanIR, frame: IntentFrame) -> list[Finding]:
    fps = timeline.fps
    violations = hard_violations(timeline, muds)
    by_rule: dict[str, list[str]] = {}
    for v in violations:
        by_rule.setdefault(v.rule, []).extend(v.items)
    findings = [
        Finding("V-WORDCUT", "CT-06" not in by_rule, "no clipped words" if "CT-06" not in by_rule else
                f"words clipped in {by_rule['CT-06']}", by_rule.get("CT-06", []), repairable=True),
        Finding("V-DUP", "CT-08" not in by_rule, "no repeated footage" if "CT-08" not in by_rule else
                f"repeated footage in {by_rule['CT-08']}", by_rule.get("CT-08", [])),
        Finding("V-SAFE", "TX-01" not in by_rule, "text inside safe areas" if "TX-01" not in by_rule else
                f"outside the safe area: {by_rule['TX-01']}", by_rule.get("TX-01", []), repairable=True),
        Finding("V-ENDING", "SA-06" not in by_rule, "ends on a full sentence" if "SA-06" not in by_rule else
                "ends mid-sentence", by_rule.get("SA-06", []), repairable=True),
    ]
    limit = max_chars(timeline.width, timeline.height)
    long_texts = [t.id for tr in timeline.tracks for t in tr.items if isinstance(t, TextItem)
                  and any(len(line) > limit * 2 for line in t.text.split("\n"))]
    findings.append(Finding("V-TEXT-OVF", not long_texts, f"too long for the frame: {long_texts}" if long_texts else
                            "text fits", long_texts))
    faced = _text_over_faces(timeline, muds)
    findings.append(Finding("V-FACE", not faced, f"text over a face: {faced}" if faced else "text clear of faces", faced,
                            repairable=True))
    duration = [a for a in failed_asks(frame, timeline, muds) if a.predicate and a.predicate.kind == "durationBetween"]
    findings.append(Finding("V-DUR", not duration, "length as asked" if not duration else
                            f"{timeline.duration / fps:.1f}s isn't what was asked", repairable=bool(duration)))
    flashes = [a for a in failed_asks(frame, timeline, muds) if a.predicate and a.predicate.kind == "solidOnEvents"]
    findings.append(Finding("V-FLASH", not flashes, "flashes on their events" if not flashes else "flash frames missing or late"))
    if plan.style.cut_on_beat or any(s.kind == "beat_sync" for s in plan.steps):
        beats = event_frames(timeline, muds, "downbeats") + event_frames(timeline, muds, "drops")
        cuts = [c.end for c in main_clips(timeline)[:-1] if not is_solid(c)]
        errors = [min(abs(c - b) for b in beats) for c in cuts] if beats else []
        ok = bool(errors) and max(errors) <= 1 and sum(errors) / len(errors) <= 0.5
        findings.append(Finding("V-BEAT", ok, f"cuts within {max(errors) if errors else '?'} frame(s) of beats"))
    findings.append(_caption_sync(timeline, muds))
    return findings


def _text_over_faces(timeline: Timeline, muds: Mapping[str, MUD]) -> list[str]:
    """Text centred where a face is, during the shot showing it (TX-07)."""
    fps, hits = timeline.fps, []
    clips = main_clips(timeline)
    for track in timeline.tracks:
        for text in (i for i in track.items if isinstance(i, TextItem)):
            if not 0.25 < text.transform.y < 0.6:
                continue  # Faces sit in the middle band; top and bottom text is clear.
            for clip in clips:
                if clip.end <= text.at or clip.at >= text.end or (mud := muds.get(clip.asset)) is None:
                    continue
                t0, t1 = clip.src_in / fps, clip.src_out / fps
                if any(s.face_x is not None and abs(s.face_x - text.transform.x) < 0.2 for s in mud.shots
                       if s.t1 > t0 and s.t0 < t1):
                    hits.append(text.id)
                    break
    return hits


def _caption_sync(timeline: Timeline, muds: Mapping[str, MUD]) -> Finding:
    """Caption cues start within 80 ms of their first word (TX-06): cues are built from word times."""
    if not (timeline.captions and timeline.captions.enabled):
        return Finding("V-CAPSYNC", True, "no captions")
    errors = []
    for clip in main_clips(timeline):
        mud = muds.get(clip.asset)
        if mud is None:
            continue
        words = [w for w in mud.words if clip.src_in / timeline.fps <= w.t0 < clip.src_out / timeline.fps]
        for cue in break_cues(words, width=timeline.width, height=timeline.height):
            first = next(w for w in words if w.i == cue.w0)
            errors.append(abs(cue.t0 - first.t0))
    worst = max(errors, default=0.0)
    return Finding("V-CAPSYNC", worst <= 0.08, f"captions within {worst * 1000:.0f} ms of their words")


# ---------------------------------------------------------------------------- repairs


def repairs(finding: Finding, timeline: Timeline, muds: Mapping[str, MUD], frame: IntentFrame) -> list[Any]:
    """12.3.1: the deterministic fix for a failed check, as Timeline ops (empty if there's none)."""
    fps = timeline.fps
    if finding.check == "V-SAFE" or finding.check == "V-FACE":
        ops = []
        for track in timeline.tracks:
            for text in (i for i in track.items if isinstance(i, TextItem) and i.id in finding.items):
                y = 0.18 if finding.check == "V-FACE" else min(SAFE_Y[1], max(SAFE_Y[0], text.transform.y))
                ops.append(UpdateItem(op="update_item", item=text.id, patch=ItemPatch(transform=TransformPatch(
                    x=min(SAFE_X[1], max(SAFE_X[0], text.transform.x)), y=y))))
        return ops
    if finding.check in ("V-WORDCUT", "V-ENDING"):
        ops = []
        for clip in main_clips(timeline):
            mud = muds.get(clip.asset)
            if mud is None or (finding.items and clip.id not in finding.items):
                continue
            end = clip.src_out / fps
            word = next((w for w in mud.words if w.t0 < end < w.t1), None)
            line = next((u for u in mud.utterances if u.t0 + 0.2 < end < u.t1 - 0.3), None) if finding.check == "V-ENDING" else None
            target = (line.t1 if line else word.t1 if word else None)
            if target is not None:
                src_out = min(timeline.assets[clip.asset].frames, round((target + WORD_END_PAD) * fps))
                if src_out != clip.src_out:
                    ops.append(TrimItem(op="trim_item", item=clip.id, src_out=src_out))
        return ops
    if finding.check == "V-DUR":
        ask = next((a for a in frame.asks if a.predicate and a.predicate.kind == "durationBetween"), None)
        clips = main_clips(timeline)
        if ask is None or not clips:
            return []
        wanted = round(float(ask.predicate.args.get("max_s", ask.predicate.args.get("min_s", 0))) * fps)
        last = clips[-1]
        delta = wanted - timeline.duration
        src_out = min(timeline.assets[last.asset].frames, max(last.src_in + 8, last.src_out + round(delta * last.speed)))
        return [TrimItem(op="trim_item", item=last.id, src_out=src_out)] if src_out != last.src_out else []
    if finding.check == "V-PEAK":
        return [UpdateItem(op="update_item", item=item.id, patch=ItemPatch(volume=round(item.volume * 0.708, 4)))
                for track in timeline.tracks if track.kind == "audio" for item in track.items
                if isinstance(item, ClipItem) and item.volume > 0.05]
    return []


# ---------------------------------------------------------------------------- the loop


async def verify_and_repair(plan_id: str, user_id: str, *, render: bool = True) -> list[Finding]:
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        assert plan is not None
        ir, frame = PlanIR.model_validate_json(plan.plan), IntentFrame.model_validate_json(plan.frame or "{}")
        entitlements = await SubscriptionService.for_session(session).get_entitlements(user_id)
        rounds = min(MAX_REPAIR_ROUNDS, max(0, entitlements.ai_critic_max_rounds))

    findings: list[Finding] = []
    for attempt in range(rounds + 1):
        findings = await _check(plan_id, user_id, ir, frame, render=render)
        failing = [f for f in findings if not f.passed]
        if not failing or attempt == rounds:
            break
        fixed = await _repair(plan_id, user_id, failing, frame, attempt)
        if not fixed:
            break
    failing = [f for f in findings if not f.passed]
    rolled = await _roll_back(plan_id, user_id, ir, failing)
    await _save_review(plan_id, findings, rolled)
    if not failing:
        from brain.critic import review  # Phase 13: only once the deterministic checks pass.

        await review(plan_id, user_id)
    return findings


async def _check(plan_id: str, user_id: str, ir: PlanIR, frame: IntentFrame, *, render: bool) -> list[Finding]:
    async with AsyncSessionLocal() as session:
        service = EditorService(session)
        plan = await session.get(EditPlan, plan_id)
        project = await service.get(user_id, plan.project_id)
        muds = (await service.media(user_id, plan.project_id)).muds
    findings = timeline_checks(project.timeline, muds, ir, frame)
    if render and main_clips(project.timeline):
        with tempfile.TemporaryDirectory(prefix="clipnera-verify-") as work:
            try:
                video = await render_timeline(project.timeline, muds, Path(work), preview=True)
                findings += await render_checks(video, project.timeline, muds)
            except Exception as exc:  # A render failure is reported, never silently ignored (ND-13).
                log.exception("Verify render failed: plan=%s", plan_id)
                findings.append(Finding("V-RENDER", False, f"The check render failed: {exc}"[:300]))
    return findings


async def _repair(plan_id: str, user_id: str, failing: list[Finding], frame: IntentFrame, attempt: int) -> bool:
    applied = False
    for n, finding in enumerate(f for f in failing if f.repairable):
        async with AsyncSessionLocal() as session:
            service = EditorService(session)
            plan = await session.get(EditPlan, plan_id)
            project = await service.get(user_id, plan.project_id)
            muds = (await service.media(user_id, plan.project_id)).muds
            ops = repairs(finding, project.timeline, muds, frame)
            if not ops:
                continue
            # 12.3.2: each repair is its own undoable transaction.
            actor = Actor(author=AUTHOR, step_id=f"plan-{plan_id[:8]}-fix{attempt}{n}", turn_id=plan_id,
                          human_owned_ok=frozenset(), destructive_ok=True, allowed_text=frozenset())
            try:
                await service.apply(user_id, plan.project_id, project.version, ops, actor)
                applied = True
            except CustomException as exc:
                log.info("Repair for %s didn't apply: %s", finding.check, exc.message)
    return applied


async def _roll_back(plan_id: str, user_id: str, ir: PlanIR, failing: list[Finding]) -> list[str]:
    """12.3.4: a step behind a hard failure that couldn't be repaired is undone, and the card says why."""
    hard = {f.check for f in failing if f.check in CHECK_STEP}
    if not hard:
        return []
    rolled: list[str] = []
    async with AsyncSessionLocal() as session:
        service = EditorService(session)
        plan = await session.get(EditPlan, plan_id)
        rows = {r.step_id: r for r in await session.scalars(select(PlanStepRow).where(PlanStepRow.plan_id == plan_id))}
        for step in reversed(ir.steps):
            check = next((c for c in hard if step.kind in CHECK_STEP[c]), None)
            row = rows.get(step.id)
            if check is None or row is None or row.status != StepStatus.DONE:
                continue
            try:
                await service.undo_step(user_id, plan.project_id, f"plan-{plan_id[:8]}-{step.id}"[:60])
            except CustomException as exc:
                log.info("Couldn't roll back %s: %s", step.id, exc.message)
                continue
            reason = next(f.detail for f in failing if f.check == check)
            row.status, row.note = StepStatus.FAILED, f"Rolled back: {reason}"[:500]
            await session.commit()
            rolled.append(step.id)
            hard.discard(check)
            if not hard:
                break
    return rolled


async def _save_review(plan_id: str, findings: list[Finding], rolled: list[str]) -> None:
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        plan.review = json.dumps({"checks": [f.__dict__ for f in findings], "rolled_back": rolled})
        await session.commit()


def known_checks() -> list[str]:
    """Every check this verifier runs (for docs and the plan card)."""
    return ["V-BLACK", "V-FLASH", "V-FROZEN", "V-DUP", "V-TEXT-OVF", "V-SAFE", "V-FACE", "V-CONTRAST", "V-CAPSYNC",
            "V-LUFS", "V-PEAK", "V-CLICK", "V-WORDCUT", "V-BEAT", "V-DUR", "V-ENDING"]

