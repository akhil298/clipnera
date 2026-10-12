"""Specialists: an LLM editor per area for steps the compiler can't express (TODO 11.1–11.2).

Each runs a short tool loop (at most 8 model calls) with the read tools, apply_edits behind
the ToolBroker, step_complete and report_issue. The ToolBroker is what makes an agent safe on
a shared timeline: every call is schema-checked, every id must exist and must have been seen in
this turn (else UNKNOWN_ID with the nearest ids), the Phase 3 guards (human ownership, budgets,
destructive edits) apply, and every result starts with APPLIED, REJECTED or CONFLICT.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, ToolBox
from brain.answer import READ_ONLY
from brain.model import EditPlan, PlanStatus
from brain.plan_ir import PlanStep
from clients.ai import get_role_client
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from editor.agent_tools import EditInput, describe
from editor.history import Actor
from editor.service import EditorService

PROMPTS = Path(__file__).parent / "prompts"
SP_COMMON = (PROMPTS / "sp_common.md").read_text(encoding="utf-8")
SPECIALIST_FOR = {
    "structure": "cut", "tighten": "cut", "beat_sync": "cut", "flash": "cut", "music": "audio", "title": "text",
    "captions": "text", "look": "color", "reframe": "reframe",
}
TOOL_NOTE = (
    "Tools here: get_timeline, the media tools, apply_edits (Timeline operations), step_complete(summary) when "
    "done, report_issue(code, message) when the step can't be done. Wherever your role text names another tool, "
    "do it with apply_edits operations."
)
LIMITS = TurnLimits(max_steps=8, seconds=180, usd=0.5, max_tokens=4000)
ID_FIELDS = ("item", "track", "asset", "new_id")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompleteInput(_Closed):
    summary: str = Field(..., min_length=1, max_length=90)


class IssueInput(_Closed):
    code: str = Field(..., max_length=40)
    message: str = Field(..., max_length=300)


@dataclass
class Outcome:
    ok: bool
    note: str
    ops: int = 0
    version: int | None = None


@dataclass
class SpecialistRun:
    service: EditorService
    user_id: str
    project_id: str
    plan_id: str
    actor: Actor
    seen: set[str] = field(default_factory=set)
    ops: int = 0
    version: int | None = None
    summary: str | None = None
    issue: str | None = None


def _ids_in(value: Any) -> set[str]:
    """Every id a tool result shows, so the broker knows what the agent has seen."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, inner in value.items():
            if key in ("id", "asset", "item", "track", "ref") and isinstance(inner, str):
                found.add(inner)
            found |= _ids_in(inner)
    elif isinstance(value, list):
        for inner in value:
            found |= _ids_in(inner)
    return found


async def _get_timeline(run: SpecialistRun, _: BaseModel) -> dict[str, Any]:
    project = await run.service.get(run.user_id, run.project_id)
    view = describe(project.version, project.timeline)
    run.seen |= _ids_in(view)
    return view


async def _apply(run: SpecialistRun, edit: EditInput) -> str:
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, run.plan_id)
        if plan is None or plan.status in (PlanStatus.PAUSED, PlanStatus.STOPPED):
            return "REJECTED PAUSED: the user paused or stopped the plan. Stop now; don't call any more tools."
    unseen = sorted({value for op in edit.ops for name in ID_FIELDS
                     if isinstance(value := getattr(op, name, None), str) and name != "new_id"} - run.seen
                    - {op.item.id for op in edit.ops if getattr(op, "op", "") == "add_item"}
                    - {op.id for op in edit.ops if getattr(op, "op", "") == "add_track"})
    if unseen:
        near = {u: difflib.get_close_matches(u, sorted(run.seen), n=3, cutoff=0.0) for u in unseen}
        return f"REJECTED UNKNOWN_ID: {', '.join(unseen)} haven't appeared in this turn. Nearest: {json.dumps(near)}"
    actor = replace(run.actor, human_owned_ok=run.actor.human_owned_ok | frozenset(edit.human_owned_ok))
    try:
        result = await run.service.apply(run.user_id, run.project_id, edit.base_version, edit.ops, actor)
    except CustomException as exc:
        state = {k: v for k, v in exc.extra.items() if k != "message"}
        prefix = "CONFLICT" if exc.code in ("CONFLICT", "STALE_VERSION") else "REJECTED"
        return f"{prefix} {exc.code}: {exc.message} {json.dumps(state, default=str)}"
    run.ops += len(edit.ops)
    run.version = result.version
    view = describe(result.version, result.timeline)
    run.seen |= _ids_in(view)
    return "APPLIED " + json.dumps(view)


async def _complete(run: SpecialistRun, args: CompleteInput) -> str:
    run.summary = args.summary
    return "Recorded. Stop now."


async def _issue(run: SpecialistRun, args: IssueInput) -> str:
    run.issue = f"{args.code}: {args.message}"
    return "Recorded. Stop now."


class _NoInput(_Closed):
    pass


def _tools() -> ToolBox:
    media = [t for t in READ_ONLY.tools() if t.name != "get_timeline"]
    return ToolBox([
        AgentTool("get_timeline", "Read the project: assets, tracks, items, times in frames.", _NoInput, _get_timeline),
        *media,
        AgentTool("apply_edits", "Change the project with Timeline operations made against base_version.", EditInput, _apply),
        AgentTool("step_complete", "Finish the step with a one-line summary the user reads.", CompleteInput, _complete),
        AgentTool("report_issue", "Say the step can't be done, and why.", IssueInput, _issue),
    ])


async def run_specialist(service: EditorService, user_id: str, project_id: str, plan_id: str, step: PlanStep,
                         actor: Actor, *, reason: str) -> Outcome:
    role = SPECIALIST_FOR[step.kind]
    system = "\n\n".join([SP_COMMON, (PROMPTS / f"specialist_{role}.md").read_text(encoding="utf-8"), TOOL_NOTE])
    run = SpecialistRun(service, user_id, project_id, plan_id, actor)
    project = await service.get(user_id, project_id)
    run.seen |= _ids_in(describe(project.version, project.timeline))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({
            "step": step.model_dump(), "why_you": reason or "This step needs judgment.",
            "timeline": describe(project.version, project.timeline),
            "human_owned_ok": sorted(actor.human_owned_ok),
        })},
    ]
    client = get_role_client("specialist")
    toolbox = _tools()
    try:
        async for _ in run_turn(client, messages, toolbox, run, LIMITS):
            if run.summary or run.issue:
                break
    finally:
        await client.close()
    if run.issue:
        return Outcome(False, run.issue, run.ops, run.version)
    if run.summary or run.ops:
        return Outcome(True, run.summary or "Done.", run.ops, run.version)
    return Outcome(False, reason or "The specialist couldn't finish this step.", run.ops, run.version)
