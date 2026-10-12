"""What the editor's op log says: who changed what, what undo and redo do next, and the
rules an agent's edit must keep.

Pure functions over the log's rows (editor.model.EditorOp), so the service can
lock the project, read its log once and decide.

* Human authority: an item a person made or changed is theirs. An agent may only
  touch it when its step names it in ``human_owned_ok``.
* Rebase: a batch made against an older version is applied on the current one,
  unless a person has since changed the same field of the same item.
* Guards: an agent can't cut most of the video, or delete a pile of clips, unless
  its step said it would, and each step and turn has an op budget.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from core.exceptions import CustomException
from editor.model import EditorOp
from editor.ops import WHOLE_ITEM, RemoveItem, Touched
from editor.timeline import ClipItem, Timeline

MAX_REMOVED_SHARE = 0.4
MAX_CLIP_DELETES = 20
# A step that rebuilds the main cut removes every clip and adds the new ones: 40 shots is ~80 ops.
STEP_OP_BUDGET = 150
TURN_OP_BUDGET = 400


@dataclass(frozen=True)
class Actor:
    """Who is editing. ``author`` is "user" for the person, "agent:<name>" for an agent."""

    author: str = "user"
    step_id: str | None = None
    turn_id: str | None = None
    # Agent only: items a person owns that this edit may change anyway, and whether the
    # step declared it would remove a lot.
    human_owned_ok: frozenset[str] = frozenset()
    destructive_ok: bool = False
    # Never-do (brain.invariants): text an agent may add (None: any, for people), and whether it may
    # change the frame size (only a reframe step of an approved plan).
    allowed_text: frozenset[str] | None = None
    may_resize: bool = False

    @property
    def is_agent(self) -> bool:
        return self.author.startswith("agent:")


HUMAN = Actor()


def touched_of(row: EditorOp) -> Touched:
    return {item: set(fields) for item, fields in json.loads(row.touched or "{}").items()}


def dump_touched(touched: Touched) -> str:
    return json.dumps({item: sorted(fields) for item, fields in sorted(touched.items())})


def _overlap(a: set[str], b: set[str]) -> bool:
    return bool(a & b) or WHOLE_ITEM in a or WHOLE_ITEM in b


# ------------------------------------------------------------------ undo and redo


@dataclass
class Group:
    """Batches that undo together: one batch, or every consecutive batch of one agent step."""

    step_id: str | None
    versions: list[int] = field(default_factory=list)


@dataclass
class Stacks:
    undo: list[Group] = field(default_factory=list)
    redo: list[Group] = field(default_factory=list)


def stacks(rows: Sequence[EditorOp]) -> Stacks:
    """Replay the log (oldest first) into what undo and redo would do next."""
    state = Stacks()
    for row in rows:
        targets = json.loads(row.targets or "[]")
        if row.kind == "edit":
            top = state.undo[-1] if state.undo else None
            if row.step_id and top and top.step_id == row.step_id:
                top.versions.append(row.version)
            else:
                state.undo.append(Group(row.step_id, [row.version]))
            state.redo.clear()
        elif row.kind == "undo":
            undone = [g for g in state.undo if set(g.versions) <= set(targets)]
            state.undo = [g for g in state.undo if g not in undone]
            state.redo.append(Group(undone[0].step_id if undone else None, targets))
        elif row.kind == "redo":
            if state.redo and state.redo[-1].versions == targets:
                group = state.redo.pop()
                # A redo is undone through its own row, whose inverse fits the Timeline it made.
                state.undo.append(Group(group.step_id, [row.version]))
    return state


def step_groups(state: Stacks, step_id: str) -> list[int]:
    """Every version of one agent step still on the undo stack, oldest first."""
    return sorted(v for g in state.undo if g.step_id == step_id for v in g.versions)


# ------------------------------------------------------------------ authority and rebase


def human_owned(rows: Iterable[EditorOp]) -> Touched:
    """Items a person made or changed, with the fields they changed."""
    owned: Touched = {}
    for row in rows:
        if not row.by_agent:
            for item, fields in touched_of(row).items():
                owned.setdefault(item, set()).update(fields)
    return owned


def check_human_owned(touched: Touched, owned: Touched, actor: Actor, current: Timeline) -> None:
    taken = sorted(item for item in touched if item in owned and item not in actor.human_owned_ok)
    if taken:
        raise CustomException(
            message=f"{', '.join(taken)} {'was' if len(taken) == 1 else 'were'} changed by the user. "
                    "Leave them alone, or list them in human_owned_ok if the user asked for this.",
            code="HUMAN_OWNED", status_code=409, extra={"items": taken, **_states(current, taken)},
        )


def check_rebase(touched: Touched, newer: Sequence[EditorOp], current: Timeline) -> None:
    """Refuse a stale batch that changes a field a person changed since it was made."""
    clashes = sorted({
        item
        for row in newer if not row.by_agent
        for item, fields in touched_of(row).items()
        if item in touched and _overlap(fields, touched[item])
    })
    if clashes:
        raise CustomException(
            message="Someone changed the same thing since you loaded the project. Reload it and try again.",
            code="CONFLICT", status_code=409, extra={"items": clashes, **_states(current, clashes)},
        )


def _states(timeline: Timeline, item_ids: Sequence[str]) -> dict[str, Any]:
    """The items as they are now, for a client to show or retry against."""
    states: dict[str, Any] = {}
    for item_id in item_ids:
        try:
            states[item_id] = timeline.find(item_id)[1].model_dump(mode="json")
        except CustomException:
            states[item_id] = None
    return {"current": states}


# ------------------------------------------------------------------ agent guards


def check_agent_guards(ops: Sequence[Any], before: Timeline, after: Timeline, actor: Actor,
                       step_ops: int, turn_ops: int) -> None:
    """``step_ops``/``turn_ops`` are the ops this step and turn already applied."""
    if not actor.destructive_ok:
        if before.duration and after.duration < before.duration * (1 - MAX_REMOVED_SHARE):
            raise CustomException(
                message=f"That would cut the video from {before.duration} to {after.duration} frames. "
                        "Declare a destructive step to remove that much.",
                code="DESTRUCTIVE_EDIT", status_code=422,
            )
        deletes = sum(1 for op in ops if isinstance(op, RemoveItem) and _is_clip(before, op.item))
        if deletes > MAX_CLIP_DELETES:
            raise CustomException(
                message=f"That deletes {deletes} clips at once; more than {MAX_CLIP_DELETES} needs a declared step.",
                code="DESTRUCTIVE_EDIT", status_code=422,
            )
    if actor.step_id and step_ops + len(ops) > STEP_OP_BUDGET:
        raise CustomException(message=f"This step has used its {STEP_OP_BUDGET} operations.",
                              code="STEP_BUDGET", status_code=422)
    if actor.turn_id and turn_ops + len(ops) > TURN_OP_BUDGET:
        raise CustomException(message=f"This turn has used its {TURN_OP_BUDGET} operations.",
                              code="TURN_BUDGET", status_code=422)


def _is_clip(timeline: Timeline, item_id: str) -> bool:
    try:
        return isinstance(timeline.find(item_id)[1], ClipItem)
    except CustomException:
        return False


def op_count(rows: Iterable[EditorOp], *, step_id: str | None = None, turn_id: str | None = None) -> int:
    return sum(
        len(json.loads(row.ops)) for row in rows
        if (step_id and row.step_id == step_id) or (turn_id and row.turn_id == turn_id)
    )
