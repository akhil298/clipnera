"""The editor agent's tools: read the open project, and change it with Timeline operations.

The model sees a compact description of the Timeline rather than its raw
JSON, and edits only through the same operations a person's hand edits use,
so every agent change is validated, logged under its own author and undoable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from agent_runtime.tools import AgentTool, ToolBox
from editor.ops import Op
from editor.service import EditorService
from editor.timeline import ClipItem, MusicItem, SfxItem, TextItem, Timeline
from motion_library.agent_tool import FIND_EDITING_ASSET, FIND_MOTION_ASSET


@dataclass
class EditorContext:
    service: EditorService
    user_id: str
    project_id: str
    author: str = "agent:editor"


class NoInput(BaseModel):
    pass


class EditInput(BaseModel):
    base_version: int = Field(..., ge=0, description="The version get_timeline or the last apply_edits returned.")
    ops: list[Op] = Field(..., min_length=1, max_length=50, description="Applied in order, all or nothing.")


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


def _item(item: ClipItem | TextItem | MusicItem | SfxItem) -> dict[str, Any]:
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
    else:
        facts.update(name=item.name)
    return facts


async def _get_timeline(context: EditorContext, _: NoInput) -> dict[str, Any]:
    project = await context.service.get(context.user_id, context.project_id)
    return describe(project.version, project.timeline)


async def _apply_edits(context: EditorContext, edit: EditInput) -> dict[str, Any]:
    result = await context.service.apply(context.user_id, context.project_id, edit.base_version, edit.ops,
                                         author=context.author)
    return describe(result.version, result.timeline)


EDITOR_TOOLS = ToolBox([
    AgentTool("get_timeline", "Read the open project: its assets, tracks and items, with times in frames.",
              NoInput, _get_timeline),
    AgentTool("apply_edits", "Change the project with Timeline operations made against base_version. "
                             "Returns the new version, or an error naming the operation that failed.",
              EditInput, _apply_edits),
    FIND_MOTION_ASSET,
    FIND_EDITING_ASSET,
])
