"""The studio agent: one model with every tool, working the open project from the chat.

It reads the timeline and the footage, edits with Timeline operations, looks at frames to check
its work, moves the studio's playhead and selection, plays ranges, opens panels, hands whole edits
to the director (a plan card) and starts exports. Everything it does streams to the chat as it
happens. A request for a whole new edit doesn't wait for the model to pick plan_edit: the router
reads every prompt (alongside the model's first reply, which waits on it) and sends those straight
to the director. Each apply_edits call is its own undoable step (``{turn_id}-{n}``) under the turn, so
the chat can undo one edit or the whole turn; the never-do list and human ownership apply in
EditorService.apply as for every agent.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, Seen, ToolBox
from brain import effects, library, server_render
from brain.answer import READ_ONLY
from brain.frames import Layer as frames_layer, grab, timecode
from brain.route import RouteDecision, digest
from brain.schema import (AgentAsk, AgentDone, AgentEdit, AgentRequest, AgentText, AgentTodo, AgentTodos,
                          AgentToolCall, AgentToolDone, AgentUi, AgentUndone, StudioPanel)
from brain.turns import clip_at, deterministic, plan_request, route_request
from clients.ai import get_role_client
from clients.services.s3 import S3
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from editor.agent_tools import EditInput, describe
from editor.history import Actor
from editor.service import EditorService
from editor.ops import AddItem, MoveItem
from editor.timeline import ClipItem, GraphicItem, SfxItem, TextItem, Timeline
from brain.render_adapter import main_track
from understanding.mud import MUD
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
    "find_effects": "Looking through the effects",
    "open_with_moment": "{label}",
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
    # The user's message this turn.
    prompt: str = ""
    # Assets with subtitles burned into the picture.
    subtitled: frozenset[str] = frozenset()
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


class HookInput(_Closed):
    start: float = Field(..., ge=0, description="Where the moment starts on the timeline now, in seconds.")
    end: float = Field(..., gt=0, description="Where it ends on the timeline now, in seconds (at most 15 s later).")
    label: str = Field("Open on the strongest moment", min_length=1, max_length=80)


class TodosInput(_Closed):
    items: list[AgentTodo] = Field(..., min_length=1, max_length=12, description="The whole list, in order.")


class AskInput(_Closed):
    question: str = Field(..., min_length=1, max_length=300)
    options: list[str] = Field(..., min_length=2, max_length=4, description="Short answers the user can tap.")


class NoInput(_Closed):
    pass


class EffectsInput(_Closed):
    kind: effects.EffectKind | None = Field(None, description="One kind, or leave out to see how many of each there are.")
    query: str = Field("", max_length=60, description="Words to look for, e.g. 'whoosh', 'slow', 'warm', 'emotional'.")


def _seconds_to_frame(timeline: Timeline, seconds: float) -> int:
    return max(0, min(round(seconds * timeline.fps), timeline.duration - 1))


HOOK_MAX_SECONDS = 15.0


def hook_ops(timeline: Timeline, muds: Mapping[str, MUD], start: float, end: float) -> list[Any]:
    """A copy of the main track's footage from ``start`` to ``end`` (its edges moved out to whole words)
    played first, and everything else moved later by its length; the cut itself stays as it is.
    Titles at the very start stay there, over the hook."""
    fps = timeline.fps
    main = main_track(timeline)
    if main is None:
        raise CustomException(message="There is no main video track to open from.", code="NO_MAIN", status_code=422)
    first, last = round(start * fps), round(min(end, start + HOOK_MAX_SECONDS) * fps)
    pieces = []
    for clip in sorted((i for i in main.items if isinstance(i, ClipItem)), key=lambda c: c.at):
        a, b = max(first, clip.at), min(last, clip.end)
        if a >= b:
            continue
        src_in, src_out = clip.src_in + round((a - clip.at) * clip.speed), clip.src_in + round((b - clip.at) * clip.speed)
        if (mud := muds.get(clip.asset)) and mud.words:
            # Whole words only: the hook never starts or stops mid-word.
            t0, t1 = src_in / fps, src_out / fps
            inside = [w for w in mud.words if w.t1 > t0 and w.t0 < t1]
            if inside:
                src_in = max(clip.src_in, min(src_in, round(inside[0].t0 * fps)))
                src_out = min(clip.src_out, max(src_out, round(inside[-1].t1 * fps) + 2))
        pieces.append(ClipItem(type="clip", id=f"hook-{uuid4().hex[:8]}", at=0, asset=clip.asset, src_in=src_in,
                               src_out=src_out, speed=clip.speed, volume=clip.volume, transform=clip.transform))
    if not pieces:
        raise CustomException(message="Nothing on the main track there to open with.", code="NO_FOOTAGE", status_code=422)
    at = 0
    for piece in pieces:
        piece.at = at
        at += piece.frames
    ops: list[Any] = []
    for track in timeline.tracks:
        # Latest first, so nothing lands on an item that hasn't moved yet.
        for item in sorted(track.items, key=lambda i: -i.at):
            if not (isinstance(item, TextItem) and item.at == 0 and track is not main):
                ops.append(MoveItem(op="move_item", item=item.id, at=item.at + at))
    return ops + [AddItem(op="add_item", track=main.id, item=piece) for piece in pieces]


async def _given_text(run: StudioRun) -> frozenset[str]:
    """What text the agent may put on screen: the user's own words in this chat, and what is said in the footage."""
    media = await run.service.media(run.user_id, run.project_id)
    said = (" ".join(w.text for w in mud.words) for mud in media.muds.values())
    return frozenset([run.prompt, *run.recent_turns, *said])


def _playable(ops: list[Any]) -> list[Any]:
    """Library sounds the agent adds carry their file, as the Sounds panel's do, so the viewer plays them."""
    for op in ops:
        if isinstance(op, AddItem) and isinstance(op.item, SfxItem) and "url" not in op.item.extra:
            if sound := library.sounds().get(op.item.name):
                op.item.extra = {**op.item.extra, "url": sound.url}
    return ops


async def _apply(run: StudioRun, edit: StudioEditInput) -> dict[str, Any]:
    run.edits += 1
    step_id = f"{run.turn_id}-{run.edits}"
    # What the user selected is what they're pointing at: the agent may change it even if they made it.
    owned_ok = frozenset(edit.human_owned_ok) | frozenset(run.selection)
    actor = Actor(author=AUTHOR, step_id=step_id, turn_id=run.turn_id, human_owned_ok=owned_ok,
                  destructive_ok=edit.declared_destructive, allowed_text=await _given_text(run))
    result = await run.service.apply(run.user_id, run.project_id, edit.base_version, _playable(edit.ops), actor)
    run.emit("edit", AgentEdit(label=edit.label, version=result.version, undo_step_id=step_id))
    return {"undo_step_id": step_id, **describe(result.version, result.timeline)}


async def _hook(run: StudioRun, args: HookInput) -> dict[str, Any]:
    project = await run.service.get(run.user_id, run.project_id)
    muds = (await run.service.media(run.user_id, run.project_id)).muds
    ops = hook_ops(project.timeline, muds, args.start, args.end)
    # The cut on the main track moves later, including clips the user placed: that is what was asked.
    moved = [op.item for op in ops if isinstance(op, MoveItem)]
    return await _apply(run, StudioEditInput(base_version=project.version, label=args.label, ops=ops, human_owned_ok=moved[:50]))


async def _undo(run: StudioRun, args: UndoInput) -> dict[str, Any]:
    if not args.undo_step_id.startswith(f"{run.turn_id}-"):
        raise CustomException(message="You can only take back your own edits from this turn.", code="NOT_YOURS",
                              status_code=422)
    result = await run.service.undo_step(run.user_id, run.project_id, args.undo_step_id)
    run.emit("undone", AgentUndone(undo_step_id=args.undo_step_id, version=result.version))
    return describe(result.version, result.timeline)


def _layers_at(timeline: Timeline, frame: int) -> list[tuple[str, frames_layer]]:
    """The flashes and shelf graphics on screen at ``frame``, named, as the stills draw them."""
    shelf, found = library.graphics(), []
    for track in timeline.tracks:
        if track.kind != "graphic" or track.hidden:
            continue
        for item in track.items:
            if not (isinstance(item, GraphicItem) and item.at <= frame < item.end):
                continue
            if isinstance(item.extra.get("solid"), str):
                found.append((f"a {item.extra['solid']} flash", ("solid", item.extra["solid"], 0.0)))
            elif graphic := shelf.get(str(item.extra.get("graphic"))):
                found.append((f"the {graphic.name} graphic", ("graphic", str(graphic.video), (frame - item.at) / timeline.fps)))
    return found


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
        layers = _layers_at(timeline, frame)
        drawn = f"; with {', '.join(name for name, _ in layers)} over it" if layers else ""
        lines.append(f"{timecode(seconds)}: clip {clip.id} (asset {clip.asset}, {source:.2f}s into it){drawn}.")
        grabs.append(grab(timeline.assets[clip.asset], source, timecode(seconds), s3, [layer for _, layer in layers]))
    jpegs = [jpeg for jpeg in await asyncio.gather(*grabs) if jpeg]
    if len(jpegs) < len(grabs):
        lines.append(f"{len(grabs) - len(jpegs)} frame(s) couldn't be read.")
    return Seen(text="\n".join(lines), jpegs=jpegs)


async def _effects(run: StudioRun, args: EffectsInput) -> dict[str, Any]:
    if args.kind is None and not args.query:
        return {"kinds": effects.counts(), "hint": "Ask for one kind, with words for what you need."}
    return {"effects": effects.find(args.kind, args.query)}


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


async def _plan(run: StudioRun, args: PlanInput, decision: RouteDecision | None = None) -> str:
    result = await plan_request(run.service, run.user_id, run.project_id, args.request, selection=run.selection,
                                playhead=run.playhead, recent_turns=run.recent_turns,
                                questions_asked=run.questions_asked, auto=run.auto, decision=decision,
                                subtitled=run.subtitled)
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
    AgentTool("open_with_moment", "Make a hook: play a copy of the moment from start to end (timeline seconds, up "
                                  "to 15 s, kept to whole words) first, and move everything else later. The rest of "
                                  "the edit is untouched. Add its zoom, sound or title after, with apply_edits.",
              HookInput, _hook),
    AgentTool("find_effects", "Search everything the editor can add: motion (zooms, pans), speed (slow motion), "
                              "transitions, sounds, animated graphics, looks, caption styles, titles and B-roll. "
                              "Each comes with what it is for and the exact operation that applies it.",
              EffectsInput, _effects),
    AgentTool("look_at_frames", "See the picture at up to 6 timeline times (stills, timecoded): the main clip with "
                                "any flash or animated graphic over it. Texts, captions and B-roll aren't drawn: "
                                "read those from the timeline.", FramesInput, _frames),
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


PROMPT_CHARS = 2000


def scoped(request: AgentRequest, fps: int) -> str:
    """The prompt with its selected range, the spot pointed at and the user's rules spelled out, so the
    router and the director keep to them."""
    notes = ""
    if request.range:
        start, end = timecode(request.range.start / fps), timecode(request.range.end / fps)
        notes += f"\n\n(This is about {start} to {end} of the timeline only; leave the rest as it is.)"
    if request.point:
        across, down = round(request.point.x * 100), round(request.point.y * 100)
        notes += (f"\n\n(This is about what is on screen {across}% across and {down}% down the frame "
                  f"at {timecode(request.playhead / fps)}; look at that frame to see it.)")
    if request.subtitled:
        notes += "\n\n(The footage already has subtitles burned into the picture: don't add captions over them.)"
    if request.rules:
        notes += "\n\nMy rules for this project, unless I say otherwise above:\n" + "\n".join(f"- {rule}" for rule in request.rules)
    if not notes:
        return request.prompt
    # Plans take at most PROMPT_CHARS: the notes always fit, the prompt gives way first.
    notes = notes[:PROMPT_CHARS - 200]
    return request.prompt[:PROMPT_CHARS - len(notes)] + notes


async def _conversation(run: StudioRun, version: int, timeline: Timeline, request: AgentRequest) -> list[dict[str, Any]]:
    media = await run.service.media(run.user_id, run.project_id)
    view = lcv.render(lcv.assets_for(media.names, media.muds, media.statuses), lcv.BUDGETS["executor"])
    messages: list[dict[str, Any]] = [{"role": "system", "content": f"{PROMPT}\n\n{view}"}]
    for exchange in request.history:
        messages.append({"role": "user", "content": exchange.prompt})
        if exchange.reply:
            messages.append({"role": "assistant", "content": exchange.reply})
    span = (request.range.start, request.range.end) if request.range else None
    studio = (f"{digest(timeline, request.selection, request.playhead, span)}\n"
              f"Project version {version}; playhead at frame {request.playhead}.")
    messages.append({"role": "user", "content": f"Studio now:\n{studio}\n\nUser message:\n{scoped(request, timeline.fps)}"})
    return messages


async def _direct(run: StudioRun, prompt: str, decision: RouteDecision) -> AsyncIterator[Event]:
    """A whole new edit, or a refusal, straight from the router's decision: the director plans it."""
    yield "tool", AgentToolCall(id=run.turn_id, name="plan_edit", label=LABELS["plan_edit"])
    message = await _plan(run, PlanInput(request=prompt), decision)
    for item in run.drain():
        yield item
    yield "tool_done", AgentToolDone(id=run.turn_id, ok=True)
    if not run.finished:
        # Not planned: refused, the footage isn't ready, or the director couldn't make a plan.
        yield "text", AgentText(text=message)
    yield "done", AgentDone(reason="handed_over" if run.finished else "answered")


async def _route(user_id: str, project_id: str, prompt: str, run: StudioRun) -> RouteDecision:
    """The router's reading of the prompt, on its own database session: it runs while the turn's
    session reads the project, and one session can't do two things at once."""
    async with AsyncSessionLocal() as session:
        return await route_request(EditorService(session), user_id, project_id, prompt, selection=run.selection,
                                   playhead=run.playhead, recent_turns=run.recent_turns)


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
                    questions_asked=request.questions_asked, auto=request.auto, prompt=request.prompt,
                    subtitled=frozenset(request.subtitled))
    prompt = scoped(request, project.timeline.fps)
    routing = asyncio.create_task(_route(user_id, project_id, prompt, run))
    client = get_role_client("studio")
    turn = run_turn(client, await _conversation(run, project.version, project.timeline, request),
                    TOOLS_AUTO if request.auto else TOOLS, run, LIMITS)
    # The model's first reply is asked for while the router reads the prompt. Nothing it asks for runs
    # before the router has answered: a tool only runs when the turn's next event is pulled.
    first = asyncio.create_task(anext(turn, None))
    try:
        decision = await routing
        if decision.intent == "new_edit" or decision.path == "refuse" or decision.safety == "block":
            first.cancel()
            async for event in _direct(run, prompt, decision):
                yield event
            return
        event = await first
        while event is not None:
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
            event = await anext(turn, None)
    finally:
        if not routing.done():
            routing.cancel()
        if not first.done():
            first.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await first
        await turn.aclose()
        await client.close()
