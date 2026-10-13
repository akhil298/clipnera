"""One prompt from the studio, end to end: route it, then take the cheapest path that can do it.

* deterministic (no model): undo, redo, "split here", "delete this";
* micro (router only): resolve the item, apply the modifier table, save as one undoable AI step;
* answer: read-only questions about the project;
* plan: anything bigger goes to the director, and comes back as a plan card to approve.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from uuid import uuid4

from brain import micro, modifiers, plans
from brain.answer import answer
from brain.context import build_context
from brain.director import direct
from brain.refs import resolve
from brain.route import RouteDecision, route
from brain.schema import TurnChoice, TurnResult
from core.exceptions import CustomException
from editor.agent_tools import EditorContext
from editor.history import HUMAN, Actor
from editor.ops import RemoveItem, SplitItem
from editor.schema import MediaAnalysisResponse
from editor.service import EditorService
from editor.timeline import ClipItem, Timeline
from understanding.lcv import untrusted

MICRO_AUTHOR = "agent:micro"
# The AI may ask once about a request; after that it decides and says what it assumed.
QUESTIONS_PER_REQUEST = 1
# Best moments quoted per file to the router.
ROUTER_MOMENTS = 2
_UNDO = re.compile(r"^\s*(undo|go back|revert that|take that back)\b", re.I)
_REDO = re.compile(r"^\s*(redo|put it back|do that again)\b", re.I)
_SPLIT = re.compile(r"\b(split|cut)\b.*\b(here|playhead|this|now)\b", re.I)
_DELETE = re.compile(r"^\s*(delete|remove)\s+(this|that|it|these|those|the selection|selected)\b", re.I)


async def handle_turn(service: EditorService, user_id: str, project_id: str, prompt: str, *,
                      selection: Sequence[str] = (), playhead: int = 0,
                      recent_turns: Sequence[str] = (), questions_asked: int = 0) -> TurnResult:
    project = await service.get(user_id, project_id)
    timeline, version = project.timeline, project.version
    may_ask = questions_asked < QUESTIONS_PER_REQUEST

    fast = await _deterministic(service, user_id, project_id, prompt, timeline, version, selection, playhead)
    if fast is not None:
        return fast

    analyses = await service.analyses(user_id, project_id)
    decision = await route(prompt, timeline, selection, playhead, recent_turns, footage=_footage(timeline, analyses))
    if decision.path == "refuse" or decision.safety == "block":
        return TurnResult(kind="refused", message="I can't help with that request.", route=decision)
    # A plan's questions are the director's to ask, after it has looked at the footage.
    if decision.clarify and decision.path != "plan" and may_ask:
        return TurnResult(kind="clarify", message=decision.clarify, route=decision)
    if decision.path == "answer":
        if decision.intent == "export_request":
            return TurnResult(kind="answer", route=decision,
                              message="Use Export at the top right to render and download your video.")
        context = EditorContext(service, user_id, project_id)
        return TurnResult(kind="answer", message=await answer(context, prompt), route=decision)
    if decision.path == "deterministic":
        if decision.intent in ("undo", "redo"):
            return await _undo_redo(service, user_id, project_id, decision.intent)
        fast = await _deterministic(service, user_id, project_id, prompt, timeline, version, selection,
                                    playhead, forced=True)
        if fast is not None:
            return fast
    if decision.path in ("micro", "deterministic"):
        result = await _micro(service, user_id, project_id, prompt, decision, timeline, version, selection, playhead)
        if result.kind != "plan_needed":
            return result
    not_ready = _not_ready(timeline, analyses)
    if not_ready:
        return TurnResult(kind="answer", message=not_ready, route=decision)
    return await _plan(service, user_id, project_id, prompt, decision, selection, playhead, recent_turns,
                       questions_asked)


def _name(timeline: Timeline, asset_id: str) -> str:
    asset = timeline.assets.get(asset_id)
    return asset.key.rsplit("/", 1)[-1] if asset else asset_id


def _footage(timeline: Timeline, analyses: Sequence[MediaAnalysisResponse]) -> str:
    """What is in the project's files, for the router: it sees no media otherwise."""
    lines = []
    for row in analyses:
        if row.asset_id not in timeline.assets:
            continue
        found = row.findings
        if found is None:
            lines.append(f"- {row.asset_id}: not analysed yet ({row.status}).")
            continue
        facts = [found.kind, f"{found.duration:.0f}s", f"{found.words} words spoken", f"{found.shots} shots"]
        if found.tempo_bpm:
            facts.append(f"music at {found.tempo_bpm:.0f} bpm")
        said = " | ".join(filter(None, [found.summary, *(moment.text for moment in found.moments[:ROUTER_MOMENTS])]))
        lines.append(f"- {row.asset_id}: {', '.join(facts)}." + (f" About and best moments: {untrusted(said)}" if said else ""))
    return "Footage:\n" + "\n".join(lines) if lines else "Footage: none uploaded yet."


def _not_ready(timeline: Timeline, analyses: Sequence[MediaAnalysisResponse]) -> str | None:
    """Why a plan can't be made from the footage yet, as a line for the user; None when it can."""
    if not timeline.assets:
        return "Add a video, music or images first: drop them here in the chat and I'll work from what's in them."
    status = {row.asset_id: row.status for row in analyses}
    waiting = [_name(timeline, asset_id) for asset_id in timeline.assets
               if status.get(asset_id, "pending") in ("pending", "running")]
    if waiting:
        return (f"I'm still going through {', '.join(waiting[:3])}. I'll edit from what is actually in it, "
                "so ask me again in a moment.")
    return None


async def _plan(service: EditorService, user_id: str, project_id: str, prompt: str, decision: RouteDecision,
                selection: Sequence[str], playhead: int, recent_turns: Sequence[str],
                questions_asked: int = 0) -> TurnResult:
    """The director plans it; the user sees a plan card to approve, edit or reject."""
    ctx = await build_context(service, user_id, project_id, selection=list(selection), playhead=playhead,
                              session=service.session)
    # The user may let the AI change what they selected, never anything else they made.
    result = await direct(service, user_id, ctx, prompt, decision, allowed_owned=set(selection),
                          recent_turns=list(recent_turns), asked_in_conversation=questions_asked,
                          may_ask=questions_asked < QUESTIONS_PER_REQUEST)
    if result.kind == "ask":
        return TurnResult(kind="clarify", message=result.question or "Which did you mean?", options=result.options,
                          route=decision)
    if result.kind == "failed":
        # Not a question: nothing for the user to answer.
        return TurnResult(kind="answer", message=result.message, route=decision)
    plan = await plans.save(service.session, user_id, project_id, prompt, ctx.version, result)
    card = await plans.card(service.session, plan)
    return TurnResult(kind="plan", message=card.summary, plan=card, route=decision)


async def _deterministic(service: EditorService, user_id: str, project_id: str, prompt: str, timeline: Timeline,
                         version: int, selection: Sequence[str], playhead: int,
                         forced: bool = False) -> TurnResult | None:
    """Commands that need no model: the selection and the playhead say what to change."""
    if _UNDO.search(prompt):
        return await _undo_redo(service, user_id, project_id, "undo")
    if _REDO.search(prompt):
        return await _undo_redo(service, user_id, project_id, "redo")
    if _SPLIT.search(prompt):
        target = _clip_at(timeline, playhead, selection)
        if target is None:
            return TurnResult(kind="clarify", message="Move the playhead over a clip to split it there.")
        if not target.at < playhead < target.end:
            return TurnResult(kind="clarify", message="The playhead is at the edge of that clip; move it inside.")
        op = SplitItem(op="split_item", item=target.id, at=playhead, new_id=f"c{uuid4().hex[:10]}")
        return await _command(service, user_id, project_id, version, [op], "Split at the playhead")
    if _DELETE.search(prompt) or (forced and re.search(r"\b(delete|remove)\b", prompt, re.I)):
        if not selection:
            return TurnResult(kind="clarify", message="Select what you want to delete first.")
        ops = [RemoveItem(op="remove_item", item=item_id) for item_id in selection]
        return await _command(service, user_id, project_id, version, ops,
                              f"Deleted {len(ops)} item{'s' if len(ops) != 1 else ''}")
    return None


async def _command(service: EditorService, user_id: str, project_id: str, version: int, ops: list,
                   label: str) -> TurnResult:
    """A direct command is the user's own edit; a refusal comes back as a message, not an error."""
    try:
        return await _save(service, user_id, project_id, version, ops, HUMAN, label)
    except CustomException as exc:
        return TurnResult(kind="clarify", message=exc.message)


def _clip_at(timeline: Timeline, playhead: int, selection: Sequence[str]) -> ClipItem | None:
    """The selected clip under the playhead, else the top visible clip there."""
    under = [
        (index, item) for index, track in enumerate(timeline.tracks) if track.kind in ("video", "overlay")
        for item in track.items if isinstance(item, ClipItem) and item.at <= playhead < item.end
    ]
    chosen = [item for _, item in under if item.id in selection] or [item for _, item in sorted(under, key=lambda p: p[0])]
    return chosen[0] if chosen else None


async def _undo_redo(service: EditorService, user_id: str, project_id: str, kind: str) -> TurnResult:
    try:
        result = await (service.undo if kind == "undo" else service.redo)(user_id, project_id)
    except CustomException as exc:
        return TurnResult(kind="clarify", message=exc.message)
    return TurnResult(kind="edit", message="Undone." if kind == "undo" else "Redone.", version=result.version)


async def _micro(service: EditorService, user_id: str, project_id: str, prompt: str, decision: RouteDecision,
                 timeline: Timeline, version: int, selection: Sequence[str], playhead: int) -> TurnResult:
    changes = modifiers.parse(prompt)
    item = None
    if any(change.prop != "look" for change in changes):
        reference = decision.references[0] if decision.references else None
        resolution = resolve(
            reference.phrase if reference else "it", timeline, selection=selection, playhead=playhead,
            recent=await service.recent_items(user_id, project_id), hint=reference.kind if reference else None,
        )
        if resolution.question:
            return TurnResult(kind="clarify", message=resolution.question, route=decision)
        if resolution.entity is None:
            return TurnResult(
                kind="choices", route=decision, message=f'Which one do you mean by "{resolution.phrase}"?',
                choices=[TurnChoice(id=e.id, label=e.label) for e in resolution.choices],
            )
        item = timeline.find(resolution.entity.id)[1]
    try:
        edit = micro.build(timeline, item, changes, prompt)
    except micro.Escalate as exc:
        return _needs_plan(decision, str(exc))
    step_id = f"micro-{uuid4().hex[:12]}"
    # The user named this item, so the agent may change it even if they made it (BLUEPRINT §3.9.6).
    actor = Actor(author=MICRO_AUTHOR, step_id=step_id, human_owned_ok=frozenset({item.id} if item else ()))
    try:
        return await _save(service, user_id, project_id, version, edit.ops, actor, edit.label, step_id, decision)
    except CustomException as exc:
        # E.g. a longer clip would run into the next one.
        return _needs_plan(decision, f"That doesn't fit as a quick change: {exc.message}")


async def _save(service: EditorService, user_id: str, project_id: str, version: int, ops: list, actor: Actor,
                label: str, step_id: str | None = None, decision: RouteDecision | None = None) -> TurnResult:
    result = await service.apply(user_id, project_id, version, ops, actor)
    return TurnResult(kind="edit", message=label, version=result.version, undo_step_id=step_id, route=decision)


def _needs_plan(decision: RouteDecision, why: str) -> TurnResult:
    """A quick edit that turned out bigger: the caller hands it to the director."""
    return TurnResult(kind="plan_needed", route=decision, message=why)
