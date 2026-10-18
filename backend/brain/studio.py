"""The studio agent: one model with every tool, working the open project from the chat.

It reads the timeline and the footage, edits with Timeline operations, looks at frames to check
its work, moves the studio's playhead and selection, plays ranges, opens panels, hands whole edits
to the director (a plan card) and starts exports. Everything it does streams to the chat as it
happens. Each apply_edits call is its own undoable step (``{turn_id}-{n}``) under the turn, so
the chat can undo one edit or the whole turn; the never-do list and human ownership apply in
EditorService.apply as for every agent.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, Seen, ToolBox
from brain import server_render
from brain.answer import READ_ONLY
from brain.frames import grab, timecode
from brain.route import digest
from brain.schema import (AgentAsk, AgentDone, AgentEdit, AgentRequest, AgentText, AgentTodo, AgentTodos,
                          AgentToolCall, AgentToolDone, AgentUi, AgentUndone, StudioPanel)
from brain.turns import clip_at, deterministic, plan_request
from clients.ai import get_role_client
from clients.services.s3 import S3
from core.exceptions import CustomException
from editor.agent_tools import EditInput, describe
from editor.history import Actor
from editor.service import EditorService
from editor.timeline import Timeline
from understanding import lcv

AUTHOR = "agent:studio"
PROMPT = (Path(__file__).parent / "prompts" / "studio.md").read_text(encoding="utf-8")
LIMITS = TurnLimits(max_steps=24, seconds=300, usd=0.75, max_tokens=4000)
MAX_FRAMES = 6
RECENT_TURNS = 3
TOOL_ERROR_CHARS = 300
STOPPED = {
    "steps": 'I stopped after the most steps one turn may take. Say "keep going" to carry on.',
    "time": 'I ran out of time for one turn. Say "keep going" to carry on.',
    "budget": 'I reached the spending limit for one turn. Say "keep going" to carry on.',
    "refused": "I can't help with that request.",
}
# The line the chat shows for each tool call; {name} is filled from the call's arguments.
LABELS = {
    "get_timeline": "Reading the timeline",
    "media_search": 'Searching the footage for "{query}"',
    "get_transcript_range": "Reading the transcript",
    "get_moments": "Finding the strongest moments",
    "get_silences": "Finding pauses",
    "get_beats": "Finding the beats",
    "apply_edits": "{label}",
    "undo_edit": "Taking back an edit",
    "look_at_frames": "Looking at the frames",
    "move_playhead": "Moving the playhead",
    "select_items": "Selecting",
    "play_preview": "Playing a preview",
    "open_panel": "Opening {panel}",
    "plan_edit": "Planning the edit",
    "start_export": "Starting the export",
    "update_todos": "Updating the to-do list",
    "ask_user": "Asking you",
}

Event = tuple[str, BaseModel]


@dataclass
class StudioRun:
    """One turn's state; also the context every tool gets (it has what EditorContext's tools read)."""

    service: EditorService
    user_id: str
    project_id: str
    turn_id: str
    selection: list[str]
    playhead: int
    recent_turns: list[str]
    questions_asked: int
    auto: bool
    edits: int = 0
    # A plan card or a question took over: the turn ends after this tool call.
    finished: bool = False
    outbox: list[Event] = field(default_factory=list)

    def emit(self, name: str, payload: BaseModel) -> None:
        self.outbox.append((name, payload))

    def drain(self) -> list[Event]:
        events, self.outbox = self.outbox, []
        return events

    async def timeline(self) -> Timeline:
        return (await self.service.get(self.user_id, self.project_id)).timeline


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudioEditInput(EditInput):
    label: str = Field(..., min_length=1, max_length=80,
                       description='What this change does, as the user reads it: "Cut 4 pauses", "Zoom on the punchline".')


class UndoInput(_Closed):
    undo_step_id: str = Field(..., max_length=80, description="The undo_step_id of one of your edits this turn.")


class FramesInput(_Closed):
    times: list[float] = Field(..., min_length=1, max_length=MAX_FRAMES, description="Timeline seconds to look at.")


class PlayheadInput(_Closed):
    seconds: float = Field(..., ge=0, description="Timeline seconds.")


class SelectInput(_Closed):
    item_ids: list[str] = Field(..., max_length=50, description="Items to select; empty clears the selection.")


class PlayInput(_Closed):
    start: float = Field(..., ge=0, description="Timeline seconds.")
    end: float = Field(..., gt=0, description="Timeline seconds; playback stops here.")


class PanelInput(_Closed):
    panel: StudioPanel


class PlanInput(_Closed):
    request: str = Field(..., min_length=1, max_length=2000,
                         description="The edit to plan: the user's words, plus anything you learned that matters.")


class TodosInput(_Closed):
    items: list[AgentTodo] = Field(..., min_length=1, max_length=12, description="The whole list, in order.")


class AskInput(_Closed):
    question: str = Field(..., min_length=1, max_length=300)
    options: list[str] = Field(..., min_length=2, max_length=4, description="Short answers the user can tap.")


class NoInput(_Closed):
    pass


def _seconds_to_frame(timeline: Timeline, seconds: float) -> int:
    return max(0, min(round(seconds * timeline.fps), timeline.duration - 1))


async def _apply(run: StudioRun, edit: StudioEditInput) -> dict[str, Any]:
    run.edits += 1
    step_id = f"{run.turn_id}-{run.edits}"
    # What the user selected is what they're pointing at: the agent may change it even if they made it.
    owned_ok = frozenset(edit.human_owned_ok) | frozenset(run.selection)
    actor = Actor(author=AUTHOR, step_id=step_id, turn_id=run.turn_id, human_owned_ok=owned_ok,
                  destructive_ok=edit.declared_destructive)
    result = await run.service.apply(run.user_id, run.project_id, edit.base_version, edit.ops, actor)
    run.emit("edit", AgentEdit(label=edit.label, version=result.version, undo_step_id=step_id))
    return {"undo_step_id": step_id, **describe(result.version, result.timeline)}


async def _undo(run: StudioRun, args: UndoInput) -> dict[str, Any]:
    if not args.undo_step_id.startswith(f"{run.turn_id}-"):
        raise CustomException(message="You can only take back your own edits from this turn.", code="NOT_YOURS",
                              status_code=422)
    result = await run.service.undo_step(run.user_id, run.project_id, args.undo_step_id)
    run.emit("undone", AgentUndone(undo_step_id=args.undo_step_id, version=result.version))
    return describe(result.version, result.timeline)


async def _frames(run: StudioRun, args: FramesInput) -> Seen:
    timeline = await run.timeline()
    s3 = S3()
    lines, grabs = [], []
    for asked in args.times:
        frame = _seconds_to_frame(timeline, asked)
        seconds = frame / timeline.fps
        clip = clip_at(timeline, frame, ())
        if clip is None:
            lines.append(f"{timecode(seconds)}: no clip on screen.")
            continue
        source = (clip.src_in + (frame - clip.at) * clip.speed) / timeline.fps
        lines.append(f"{timecode(seconds)}: clip {clip.id} (asset {clip.asset}, {source:.2f}s into it).")
        grabs.append(grab(timeline.assets[clip.asset], source, timecode(seconds), s3))
    jpegs = [jpeg for jpeg in await asyncio.gather(*grabs) if jpeg]
    if len(jpegs) < len(grabs):
        lines.append(f"{len(grabs) - len(jpegs)} frame(s) couldn't be read.")
    return Seen(text="\n".join(lines), jpegs=jpegs)


async def _seek(run: StudioRun, args: PlayheadInput) -> str:
    timeline = await run.timeline()
    seconds = _seconds_to_frame(timeline, args.seconds) / timeline.fps
    run.emit("ui", AgentUi(action="seek", seconds=seconds))
    return f"The playhead is at {timecode(seconds)}."


async def _select(run: StudioRun, args: SelectInput) -> str:
    timeline = await run.timeline()
    known = {item.id for track in timeline.tracks for item in track.items}
    unknown = [item_id for item_id in args.item_ids if item_id not in known]
    if unknown:
        raise CustomException(message=f"There are no items {', '.join(unknown)}.", code="UNKNOWN_ITEM",
                              status_code=422)
    run.emit("ui", AgentUi(action="select", item_ids=args.item_ids))
    return f"Selected {len(args.item_ids)} item(s)." if args.item_ids else "Cleared the selection."


async def _play(run: StudioRun, args: PlayInput) -> str:
    if args.end <= args.start:
        raise CustomException(message="end must come after start.", code="BAD_RANGE", status_code=422)
    run.emit("ui", AgentUi(action="play", seconds=args.start, end=args.end))
    return f"Playing {timecode(args.start)} to {timecode(args.end)} for the user."


async def _panel(run: StudioRun, args: PanelInput) -> str:
    run.emit("ui", AgentUi(action="panel", panel=args.panel))
    return f"The {args.panel} panel is open."


async def _plan(run: StudioRun, args: PlanInput) -> str:
    result = await plan_request(run.service, run.user_id, run.project_id, args.request, selection=run.selection,
                                playhead=run.playhead, recent_turns=run.recent_turns,
                                questions_asked=run.questions_asked, auto=run.auto)
    if result.plan is not None:
        run.emit("plan", result.plan)
        run.finished = True
        running = result.plan.status in ("approved", "running")
        return (f"The plan card is in the chat ({result.plan.summary}). "
                + ("It is running now." if running else "It waits for the user to approve it."))
    if result.kind == "clarify":
        run.emit("ask", AgentAsk(question=result.message, options=result.options))
        run.finished = True
        return "The user was asked a question about the edit."
    return result.message


async def _export(run: StudioRun, _: NoInput) -> str:
    render = await server_render.start(run.service.session, run.user_id, run.project_id)
    run.emit("render", server_render.status(render))
    return "The export has started; the chat shows its progress and the download link."


async def _todos(run: StudioRun, args: TodosInput) -> str:
    run.emit("todos", AgentTodos(items=args.items))
    return "Updated."


async def _ask(run: StudioRun, args: AskInput) -> str:
    run.emit("ask", AgentAsk(question=args.question, options=args.options))
    run.finished = True
    return "Asked."


_TOOLS = [
    # get_timeline and the media tools: search, transcript, moments, silences, beats.
    *READ_ONLY.tools(),
    AgentTool("apply_edits", "Change the project with Timeline operations made against base_version, as one "
                             "undoable step. Returns its undo_step_id and the new timeline, or why it was refused.",
              StudioEditInput, _apply),
    AgentTool("undo_edit", "Take back one of your own edits from this turn.", UndoInput, _undo),
    AgentTool("look_at_frames", "See the footage on screen at up to 6 timeline times (stills, timecoded). "
                                "Shows clips only: read texts and captions from the timeline.", FramesInput, _frames),
    AgentTool("move_playhead", "Move the studio's playhead, to show the user a moment.", PlayheadInput, _seek),
    AgentTool("select_items", "Select items on the studio's timeline, to point at them.", SelectInput, _select),
    AgentTool("play_preview", "Play a range of the timeline in the studio's preview for the user.", PlayInput, _play),
    AgentTool("open_panel", "Open one of the studio's side panels.", PanelInput, _panel),
    AgentTool("plan_edit", "Have the director plan a whole edit or a cut-down (zooms, captions, music, sound). "
                           "The plan card shows in the chat and your turn ends.", PlanInput, _plan),
    AgentTool("start_export", "Render the saved project to a video file on the server. Only when the user asks.",
              NoInput, _export),
    AgentTool("update_todos", "Show your to-do list for a longer job; send the whole list each time.", TodosInput, _todos),
    AgentTool("ask_user", "Ask one question with 2-4 short options; your turn ends.", AskInput, _ask),
]
TOOLS = ToolBox(_TOOLS)
# Auto mode never asks.
TOOLS_AUTO = ToolBox([tool for tool in _TOOLS if tool.name != "ask_user"])


def label(name: str, arguments: dict[str, Any]) -> str:
    """The line the chat shows for a tool call."""
    text = LABELS.get(name, name).format_map(defaultdict(str, arguments)).strip()
    return text[:80] or name


async def _conversation(run: StudioRun, version: int, timeline: Timeline, request: AgentRequest) -> list[dict[str, Any]]:
    media = await run.service.media(run.user_id, run.project_id)
    view = lcv.render(lcv.assets_for(media.names, media.muds, media.statuses), lcv.BUDGETS["executor"])
    messages: list[dict[str, Any]] = [{"role": "system", "content": f"{PROMPT}\n\n{view}"}]
    for exchange in request.history:
        messages.append({"role": "user", "content": exchange.prompt})
        if exchange.reply:
            messages.append({"role": "assistant", "content": exchange.reply})
    studio = (f"{digest(timeline, request.selection, request.playhead)}\n"
              f"Project version {version}; playhead at frame {request.playhead}.")
    messages.append({"role": "user", "content": f"Studio now:\n{studio}\n\nUser message:\n{request.prompt}"})
    return messages


async def stream(service: EditorService, user_id: str, project_id: str, request: AgentRequest) -> AsyncIterator[Event]:
    """One prompt, worked through: (event name, payload) pairs, ending with ``done``."""
    project = await service.get(user_id, project_id)
    fast = await deterministic(service, user_id, project_id, request.prompt, project.timeline, project.version,
                               request.selection, request.playhead)
    if fast is not None:
        yield "result", fast
        yield "done", AgentDone(reason="answered")
        return
    run = StudioRun(service, user_id, project_id, turn_id=f"studio-{uuid4().hex[:12]}",
                    selection=list(request.selection), playhead=request.playhead,
                    recent_turns=[e.prompt for e in request.history][-RECENT_TURNS:],
                    questions_asked=request.questions_asked, auto=request.auto)
    messages = await _conversation(run, project.version, project.timeline, request)
    client = get_role_client("studio")
    try:
        async for event in run_turn(client, messages, TOOLS_AUTO if request.auto else TOOLS, run, LIMITS):
            if event.type == "text":
                yield "text", AgentText(text=event.data["text"])
            elif event.type == "tool_call":
                # Hand edits and running plans save in other sessions: read the project fresh for this call.
                service.session.expire_all()
                yield "tool", AgentToolCall(id=event.data["id"], name=event.data["name"],
                                            label=label(event.data["name"], event.data["arguments"]))
            elif event.type == "tool_result":
                for item in run.drain():
                    yield item
                error = None if event.data["ok"] else event.data["content"][:TOOL_ERROR_CHARS]
                yield "tool_done", AgentToolDone(id=event.data["id"], ok=event.data["ok"], error=error)
                if run.finished:
                    yield "done", AgentDone(reason="handed_over")
                    return
            else:
                reason: Literal["answered", "steps", "time", "budget", "refused"] = event.data["reason"]
                yield "done", AgentDone(reason=reason, message=STOPPED.get(reason))
    finally:
        await client.close()
