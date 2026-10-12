"""The editor agent's tools: read the open project, and change it with Timeline operations.

The model sees a compact description of the Timeline rather than its raw
JSON, and edits only through the same operations a person's hand edits use,
so every agent change is validated, logged under its own author and undoable.
Items the user made or changed are off limits unless the edit names them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from agent_runtime.tools import AgentTool, ToolBox
from editor.history import Actor
from editor.ops import Op
from editor.service import EditorService
from editor.timeline import ClipItem, GraphicItem, MusicItem, SfxItem, TextItem, Timeline
from understanding.agent_tools import MEDIA_TOOLS


@dataclass
class EditorContext:
    service: EditorService
    user_id: str
    project_id: str
    author: str = "agent:editor"
    # The plan step and turn this agent is working on, when it runs one (budgets and step undo).
    step_id: str | None = None
    turn_id: str | None = None


class NoInput(BaseModel):
    pass


class EditInput(BaseModel):
    base_version: int = Field(..., ge=0, description="The version get_timeline or the last apply_edits returned.")
    ops: list[Op] = Field(..., min_length=1, max_length=50, description="Applied in order, all or nothing.")
    human_owned_ok: list[str] = Field(
        default_factory=list, max_length=50,
        description="Ids of items the user made or changed that this edit must change, because the user asked "
                    "for exactly that. Anything else the user touched is refused with HUMAN_OWNED.",
    )
    declared_destructive: bool = Field(
        False, description="True only when the user asked to cut most of the video or delete many clips.",
    )


def describe(version: int, timeline: Timeline) -> dict[str, Any]:
    """The Timeline as the model reads it: one line of facts per item, times in frames."""
    return {
        "version": version,
        "fps": timeline.fps,
        "size": [timeline.width, timeline.height],
        "duration_frames": timeline.duration,
        "look": timeline.look,
        "assets": [{"id": a.id, "kind": a.kind, "frames": a.frames, "has_audio": a.has_audio} for a in timeline.assets.values()],
        "tracks": [{"id": t.id, "kind": t.kind, "items": [_item(i) for i in t.items]} for t in timeline.tracks],
        "captions": timeline.captions.model_dump() if timeline.captions else None,
    }


def _item(item: ClipItem | TextItem | MusicItem | SfxItem | GraphicItem) -> dict[str, Any]:
    facts: dict[str, Any] = {"id": item.id, "type": item.type, "at": item.at, "end": item.end}
    if isinstance(item, ClipItem):
        facts.update(asset=item.asset, src=[item.src_in, item.src_out], speed=item.speed,
                     scale=item.transform.scale)
        if item.keyframes:
            facts["keyframes"] = {prop: [[p.f, p.v] for p in points] for prop, points in item.keyframes.items()}
    elif isinstance(item, TextItem):
        facts.update(text=item.text, style=item.style)
    elif isinstance(item, MusicItem):
        facts.update(track=item.track, gain_db=item.gain_db)
    elif isinstance(item, SfxItem):
        facts.update(name=item.name)
    return facts


async def _get_timeline(context: EditorContext, _: NoInput) -> dict[str, Any]:
    project = await context.service.get(context.user_id, context.project_id)
    return describe(project.version, project.timeline)


async def _apply_edits(context: EditorContext, edit: EditInput) -> dict[str, Any]:
    actor = Actor(author=context.author, step_id=context.step_id, turn_id=context.turn_id,
                  human_owned_ok=frozenset(edit.human_owned_ok), destructive_ok=edit.declared_destructive)
    result = await context.service.apply(context.user_id, context.project_id, edit.base_version, edit.ops, actor)
    return describe(result.version, result.timeline)


EDITOR_TOOLS = ToolBox([
    AgentTool("get_timeline", "Read the open project: its assets, tracks and items, with times in frames.",
              NoInput, _get_timeline),
    AgentTool("apply_edits", "Change the project with Timeline operations made against base_version. "
                             "Returns the new version, or an error naming the operation that failed.",
              EditInput, _apply_edits),
    # Looking into the footage: search, transcript, moments, silences, beats (understanding/).
    *MEDIA_TOOLS,
])
