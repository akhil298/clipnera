"""The critic (TODO Phase 13): a vision model reviews contact sheets of the finished edit.

It runs only after the deterministic checks pass (brain.verify). Frames are taken at every shot
and every text in/out (at most 48), tiled 4×4 with burned-in timecodes. The critic submits
pass / fix / replan with issues: fixable kinds go through the same deterministic repairs as the
verifier; a replan asks the director once for a revised plan, shown to the user as a new card.
Each review round is priced (brain.credits.CRITIC_ROUND).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, ToolBox
from brain.frames import stamp, timecode
from brain.intent import IntentFrame
from brain.model import EditPlan
from brain.plan_ir import PlanIR
from brain.render_adapter import main_clips, render_timeline
from clients.ai import get_role_client
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from editor.agent_tools import describe
from editor.service import EditorService
from editor.timeline import TextItem, Timeline

log = get_logger(__name__)

PROMPT = (Path(__file__).parent / "prompts" / "critic.md").read_text(encoding="utf-8")
GRID = 4
MAX_FRAMES = 48
TILE = (180, 320)
LIMITS = TurnLimits(max_steps=2, seconds=120, usd=0.4, max_tokens=3000)
ISSUE_TO_CHECK = {"text_safe_area": "V-SAFE", "text_over_face": "V-FACE", "word_cut": "V-WORDCUT",
                  "ending": "V-ENDING", "duration": "V-DUR", "too_loud": "V-PEAK"}


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Issue(_Closed):
    step_id: str = Field(..., max_length=40)
    severity: Literal["high", "medium", "low"]
    t0: float = Field(..., ge=0)
    t1: float = Field(..., ge=0)
    kind: Literal["text_safe_area", "text_over_face", "word_cut", "ending", "duration", "too_loud", "requirement",
                  "visual", "story", "other"]
    problem: str = Field(..., max_length=300)
    fix: str = Field(..., max_length=300)


class ReviewInput(_Closed):
    verdict: Literal["pass", "fix", "replan"]
    issues: list[Issue] = Field(default_factory=list, max_length=20)
    summary: str = Field(..., max_length=200)


def sample_times(timeline: Timeline) -> list[float]:
    """Seconds to look at: the middle of every shot, and every text's start and end."""
    fps = timeline.fps
    times = [(c.at + c.frames / 2) / fps for c in main_clips(timeline)]
    times += [t for track in timeline.tracks for item in track.items if isinstance(item, TextItem)
              for t in ((item.at + 2) / fps, (item.end - 2) / fps)]
    unique = sorted({round(t, 2) for t in times if 0 <= t < timeline.duration / fps})
    if len(unique) > MAX_FRAMES:
        step = len(unique) / MAX_FRAMES
        unique = [unique[int(i * step)] for i in range(MAX_FRAMES)]
    return unique


def contact_sheets(video: Path, times: list[float]) -> list[bytes]:
    """4×4 JPEG sheets of the frames at ``times``, each tile labelled with its timecode."""
    capture = cv2.VideoCapture(str(video))
    tiles = []
    for t in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = capture.read()
        tile = cv2.resize(frame, TILE) if ok else np.zeros((TILE[1], TILE[0], 3), np.uint8)
        tiles.append(stamp(tile, timecode(t)))
    capture.release()
    sheets = []
    for first in range(0, len(tiles), GRID * GRID):
        group = tiles[first:first + GRID * GRID]
        group += [np.zeros_like(group[0])] * (GRID * GRID - len(group))
        rows = [np.hstack(group[r * GRID:(r + 1) * GRID]) for r in range(GRID)]
        ok, jpeg = cv2.imencode(".jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            sheets.append(jpeg.tobytes())
    return sheets


async def _submit(state: dict[str, Any], review: ReviewInput) -> str:
    state["review"] = review
    return "Recorded."


async def review(plan_id: str, user_id: str, video: Path | None = None) -> ReviewInput | None:
    """The critic's review of the cut as it stands: from ``video`` (the verifier's check render of it), or a fresh render."""
    async with AsyncSessionLocal() as session:
        service = EditorService(session)
        plan = await session.get(EditPlan, plan_id)
        if plan is None:
            return None
        ir, frame = PlanIR.model_validate_json(plan.plan), IntentFrame.model_validate_json(plan.frame or "{}")
        project = await service.get(user_id, plan.project_id)
        muds = (await service.media(user_id, plan.project_id)).muds
        lint = json.loads(plan.review or "{}")
    if not main_clips(project.timeline):
        return None
    with tempfile.TemporaryDirectory(prefix="clipnera-critic-") as work:
        try:
            video = video or await render_timeline(project.timeline, muds, Path(work), preview=True)
        except Exception:
            log.exception("Critic render failed: plan=%s", plan_id)
            return None
        sheets = contact_sheets(video, sample_times(project.timeline))
    client = get_role_client("critic")
    state: dict[str, Any] = {}
    body = json.dumps({"request": plan.prompt, "asks": [a.model_dump() for a in frame.asks],
                       "plan": {"summary": ir.summary, "steps": [s.model_dump() for s in ir.steps]},
                       "edl": describe(project.version, project.timeline), "qa_lint": lint.get("checks", [])},
                      default=str)
    messages = [{"role": "system", "content": PROMPT + "\n\nIssue kinds: " + ", ".join(Issue.model_fields["kind"].annotation.__args__)},  # type: ignore[union-attr]
                client.image_message("Review this edit. Call review_submit once.\n" + body, sheets)]
    try:
        async for _ in run_turn(client, messages, ToolBox([AgentTool("review_submit", "Submit the review once.",
                                                                     ReviewInput, _submit)]), state, LIMITS):
            if "review" in state:
                break
    finally:
        await client.close()
    verdict: ReviewInput | None = state.get("review")
    await _record(plan_id, verdict)
    if verdict is not None:
        await _act(plan_id, user_id, verdict, frame)
    return verdict


async def _record(plan_id: str, verdict: ReviewInput | None) -> None:
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        stored = json.loads(plan.review or "{}")
        stored["critic"] = verdict.model_dump() if verdict else {"verdict": "unavailable"}
        plan.review = json.dumps(stored)
        plan.review_rounds += 1
        await session.commit()


async def _act(plan_id: str, user_id: str, verdict: ReviewInput, frame: IntentFrame) -> None:
    """13.2.3: fixable issues are repaired; a replan asks the director once for a revised plan."""
    from brain.verify import Finding, _repair  # The verifier's repairs, reused so fixes stay deterministic.

    fixes = [Finding(ISSUE_TO_CHECK[i.kind], False, i.problem, repairable=True) for i in verdict.issues
             if i.kind in ISSUE_TO_CHECK and i.severity != "low"]
    if fixes:
        await _repair(plan_id, user_id, fixes, frame, attempt=9)
    if verdict.verdict == "replan":
        await _replan(plan_id, user_id, verdict)


async def _replan(plan_id: str, user_id: str, verdict: ReviewInput) -> None:
    from brain.context import build_context
    from brain.director import direct
    from brain.plans import save
    from brain.route import Constraints, RouteDecision

    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        stored = json.loads(plan.review or "{}")
        if stored.get("replanned"):
            return  # Once per turn.
        service = EditorService(session)
        ctx = await build_context(service, user_id, plan.project_id, selection=[], playhead=0, session=session)
        notes = "; ".join(f"{i.severity}: {i.problem} → {i.fix}" for i in verdict.issues)
        prompt = f"{plan.prompt}\n\nThe critic reviewed the result and asks for a re-plan: {notes}"
        decision = RouteDecision(intent="refine_edit", path="plan", agents=[], references=[], complexity=3,
                                 constraints=Constraints(targetDurationSec=None, aspect=None, mood=None, mustKeep=[]),
                                 clarify=None, safety="ok", preference=None)
        result = await direct(service, user_id, ctx, prompt, decision, allowed_owned=set(), recent_turns=[plan.prompt])
        if result.kind == "plan":
            revised = await save(session, user_id, plan.project_id, plan.prompt, ctx.version, result, ctx.muds)
            stored["replanned"] = revised.id
        else:
            stored["replanned"] = "failed"
        plan = await session.get(EditPlan, plan_id)
        plan.review = json.dumps(stored)
        await session.commit()
