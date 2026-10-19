"""The studio agent (brain/studio.py) against a real Postgres, with a scripted model.

Skipped unless TEST_DATABASE_URL points at a disposable database (see test_editor_db.py).
"""

from __future__ import annotations

import asyncio

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from brain import library, studio
from brain.route import Constraints, RouteDecision
from brain.schema import AgentRequest, PlanCard, TurnResult
from clients.ai.base import BaseAI, ToolCall, ToolReply, ToolResult
from editor.model import EditorOp
from editor.schema import EditorProjectCreate
from editor.service import EditorService
from test_editor_db import OPS, clip, clip_asset, no_background_jobs, user  # noqa: F401  fixtures and helpers
from test_plans_db import TEST_DATABASE_URL, db  # noqa: F401  the shared database fixture

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")]

TURN = "studio-0123456789ab"
ZOOM = {"op": "update_item", "item": "c1", "patch": {"keyframes": {"scale": [{"f": 0, "v": 1}, {"f": 12, "v": 1.15}]}}}


class Scripted(BaseAI):
    def __init__(self, *replies: ToolReply) -> None:
        self.replies = list(replies)
        self.seen: list[list[dict[str, Any]]] = []

    async def chat_with_tools(self, messages, tools, *, max_tokens=4096) -> ToolReply:
        self.seen.append(list(messages))
        return self.replies.pop(0)

    def tool_results(self, results: list[ToolResult]) -> list[dict[str, Any]]:
        return [{"role": "tool", "tool_call_id": r.call_id, "content": r.content} for r in results]

    async def chat(self, messages, **kwargs): raise NotImplementedError

    async def stream_chat(self, messages, **kwargs): raise NotImplementedError

    async def close(self) -> None: ...


def calls(*pairs: tuple[str, dict]) -> ToolReply:
    return ToolReply(text="", calls=[ToolCall(f"t{i}", name, args) for i, (name, args) in enumerate(pairs)],
                     message={"role": "assistant", "content": "calling"})


def answer(text: str) -> ToolReply:
    return ToolReply(text=text, message={"role": "assistant", "content": text})


def decision(intent: str = "refine_edit", path: str = "micro") -> RouteDecision:
    return RouteDecision(intent=intent, path=path, agents=[], references=[], complexity=2, clarify=None, safety="ok",
                         preference=None, constraints=Constraints(targetDurationSec=None, aspect=None, mood=None, mustKeep=[]))


@pytest.fixture(autouse=True)
def fixed_turn_id(monkeypatch):
    monkeypatch.setattr(studio, "uuid4", lambda: SimpleNamespace(hex=TURN.removeprefix("studio-") + "ffff"))


@pytest.fixture(autouse=True)
def router(monkeypatch):
    """The router's reading of every prompt; a test sets ``router.decision`` for another."""
    state = SimpleNamespace(decision=decision())

    async def route_request(*args, **kwargs) -> RouteDecision:
        return state.decision

    monkeypatch.setattr(studio, "route_request", route_request)
    return state


async def project_with_two_clips(maker) -> tuple[str, str]:
    owner = await user(maker)
    async with maker() as session:
        service = EditorService(session)
        project = await service.create(owner, EditorProjectCreate())
        await service.apply(owner, project.id, 0, OPS.validate_python([clip_asset(owner, project.id), clip("c1", 0), clip("c2", 90)]))
    return owner, project.id


async def run(maker, monkeypatch, owner: str, project_id: str, model: BaseAI, **request: Any) -> list[tuple[str, dict]]:
    monkeypatch.setattr(studio, "get_role_client", lambda role: model)
    async with maker() as session:
        stream = studio.stream(EditorService(session), owner, project_id, AgentRequest(**{"prompt": "go", **request}))
        return [(name, payload.model_dump(mode="json")) async for name, payload in stream]


async def test_the_agent_drives_the_studio_edits_and_takes_an_edit_back(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    model = Scripted(
        calls(("get_timeline", {}), ("move_playhead", {"seconds": 1.0}), ("select_items", {"item_ids": ["c1"]})),
        calls(("apply_edits", {"base_version": 1, "label": "Zoom in on the opening", "ops": [ZOOM]})),
        calls(("undo_edit", {"undo_step_id": f"{TURN}-1"})),
        answer("Zoomed in, then took it back."),
    )
    events = await run(db, monkeypatch, owner, project_id, model, selection=["c1"], playhead=30)

    assert [name for name, _ in events] == [
        "tool", "tool_done", "tool", "ui", "tool_done", "tool", "ui", "tool_done",
        "tool", "edit", "tool_done", "tool", "undone", "tool_done", "text", "done",
    ]
    by_name = {name: data for name, data in events}
    assert events[3][1] == {"action": "seek", "seconds": 1.0, "end": None, "item_ids": [], "panel": None}
    assert events[6][1]["item_ids"] == ["c1"]
    assert events[8][1]["label"] == "Zoom in on the opening"
    assert by_name["edit"] == {"label": "Zoom in on the opening", "version": 2, "undo_step_id": f"{TURN}-1"}
    assert by_name["undone"]["undo_step_id"] == f"{TURN}-1"
    assert by_name["done"] == {"reason": "answered", "message": None}
    # The model saw where the studio was: the selection and the playhead.
    assert "playhead at frame 30" in model.seen[0][-1]["content"] and "clip c1" in model.seen[0][-1]["content"]
    async with db() as session:
        rows = (await session.execute(select(EditorOp).order_by(EditorOp.version))).scalars().all()
    assert [(row.author, row.step_id, row.turn_id) for row in rows[:2]] == [("user", None, None), ("agent:studio", f"{TURN}-1", TURN)]


async def test_what_the_user_made_stays_theirs_unless_they_point_at_it(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    model = Scripted(calls(("apply_edits", {"base_version": 1, "label": "Zoom", "ops": [ZOOM]})), answer("I left your clip alone."))
    events = await run(db, monkeypatch, owner, project_id, model)
    done = next(data for name, data in events if name == "tool_done")
    assert not done["ok"] and done["error"].startswith("HUMAN_OWNED")
    assert "edit" not in [name for name, _ in events]


async def test_a_question_ends_the_turn(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    model = Scripted(calls(("ask_user", {"question": "Which part?", "options": ["The intro", "The ending"]})))
    events = await run(db, monkeypatch, owner, project_id, model)
    assert events[-2:] == [("tool_done", {"id": "t0", "ok": True, "error": None}),
                           ("done", {"reason": "handed_over", "message": None})]
    assert ("ask", {"question": "Which part?", "options": ["The intro", "The ending"]}) in events
    assert len(model.seen) == 1


async def test_auto_mode_has_no_question_tool_and_undo_is_for_this_turn_only(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    model = Scripted(calls(("ask_user", {"question": "?", "options": ["a", "b"]}), ("undo_edit", {"undo_step_id": "studio-other-1"})),
                     answer("Carrying on."))
    events = await run(db, monkeypatch, owner, project_id, model, auto=True)
    errors = [data["error"] for name, data in events if name == "tool_done"]
    assert errors[0] == "There is no tool called ask_user." and errors[1].startswith("NOT_YOURS")


async def test_commands_that_need_no_model_answer_at_once(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    events = await run(db, monkeypatch, owner, project_id, Scripted(), prompt="delete this", selection=["c2"])
    assert [name for name, _ in events] == ["result", "done"]
    assert events[0][1]["kind"] == "edit" and events[0][1]["version"] == 2


async def test_frames_are_read_from_the_clip_on_screen(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    grabbed: list[tuple[str, float, str]] = []

    async def fake_grab(asset, seconds, label, s3=None, layers=None) -> bytes:
        grabbed.append((asset.id, round(seconds, 2), label))
        return b"jpeg"

    monkeypatch.setattr(studio, "grab", fake_grab)
    monkeypatch.setattr(studio, "S3", lambda: None)
    model = Scripted(calls(("look_at_frames", {"times": [1.0, 4.5, 60.0]})), answer("Both shots are framed well."))
    await run(db, monkeypatch, owner, project_id, model)
    # c2 starts at frame 90 (3 s): 4.5 s is 1.5 s into its source; 60 s is past the end, so the last frame.
    assert grabbed == [("a1", 1.0, "0:01.00"), ("a1", 1.5, "0:04.50"), ("a1", 2.97, "0:05.97")]
    tool_result, pictures = model.seen[1][-2:]
    assert "clip c1" in tool_result["content"] and "clip c2" in tool_result["content"]
    assert len([part for part in pictures["content"] if part["type"] == "image_url"]) == 3


async def test_a_whole_new_edit_goes_to_the_director_without_the_model(db, monkeypatch, router) -> None:
    owner, project_id = await project_with_two_clips(db)
    router.decision = decision("new_edit", "plan")
    card = PlanCard(id="p1", status="approved", title="Full edit", summary="Everything said, tightened.", result_line="",
                    credits=3, credits_charged=0, steps=[], assumptions=[], warnings=[], premium=[], ghost=[], fps=30,
                    runner_up_title=None, error=None)
    seen: dict[str, Any] = {}

    async def plan_request(*args, **kwargs) -> TurnResult:
        seen.update(kwargs)
        return TurnResult(kind="plan", message=card.summary, plan=card)

    monkeypatch.setattr(studio, "plan_request", plan_request)
    events = await run(db, monkeypatch, owner, project_id, Scripted(), prompt="Edit the full video.", auto=True)
    assert [name for name, _ in events] == ["tool", "plan", "tool_done", "done"]
    assert events[0][1]["label"] == "Planning the edit" and events[-1][1]["reason"] == "handed_over"
    assert seen["decision"] is router.decision and seen["auto"] is True


async def test_the_model_starts_while_the_router_reads_but_acts_only_once_it_has(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    asked = asyncio.Event()

    class Eager(Scripted):
        async def chat_with_tools(self, messages, tools, *, max_tokens=4096) -> ToolReply:
            asked.set()
            return await super().chat_with_tools(messages, tools, max_tokens=max_tokens)

    async def route_request(*args, **kwargs) -> RouteDecision:
        # The router answers only after the model has been asked: both were working at once.
        await asyncio.wait_for(asked.wait(), 5)
        return decision("new_edit", "plan")

    async def plan_request(*args, **kwargs) -> TurnResult:
        return TurnResult(kind="answer", message="Planned.")

    monkeypatch.setattr(studio, "route_request", route_request)
    monkeypatch.setattr(studio, "plan_request", plan_request)
    model = Eager(calls(("apply_edits", {"base_version": 1, "label": "Zoom", "ops": [ZOOM]})))
    events = await run(db, monkeypatch, owner, project_id, model, prompt="Edit the full video.")
    assert [name for name, _ in events] == ["tool", "tool_done", "text", "done"]
    # The model wanted to edit; the router sent the request to the director, so nothing was applied.
    async with db() as session:
        assert (await EditorService(session).get(owner, project_id)).version == 1


async def test_a_sound_the_agent_adds_carries_its_file_so_the_viewer_plays_it(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    sfx = {"op": "add_item", "track": "a9", "item": {"type": "sfx", "id": "s1", "at": 30, "name": "pop", "dur": 9}}
    model = Scripted(
        calls(("apply_edits", {"base_version": 1, "label": "Pop", "ops": [{"op": "add_track", "id": "a9", "kind": "audio"}, sfx]})),
        answer("Added a pop."),
    )
    await run(db, monkeypatch, owner, project_id, model)
    async with db() as session:
        timeline = (await EditorService(session).get(owner, project_id)).timeline
    item = next(i for t in timeline.tracks for i in t.items if i.id == "s1")
    assert item.extra["url"] == library.sounds()["pop"].url


async def test_a_title_the_user_asked_for_goes_in_and_an_invented_one_doesnt(db, monkeypatch) -> None:
    owner, project_id = await project_with_two_clips(db)
    title = lambda text: {"op": "add_item", "track": "t9", "item": {"type": "text", "id": "x1", "at": 0, "text": text,  # noqa: E731
                                                                    "style": "title", "dur": 60, "transform": {"y": 0.3}}}
    model = Scripted(
        calls(("apply_edits", {"base_version": 1, "label": "Made up", "ops": [{"op": "add_track", "id": "t9", "kind": "text"}, title("Best video ever")]})),
        calls(("apply_edits", {"base_version": 1, "label": "Title", "ops": [{"op": "add_track", "id": "t9", "kind": "text"}, title("57 YEARS APART")]})),
        answer("Added the title."),
    )
    events = await run(db, monkeypatch, owner, project_id, model, prompt="Put a big title at the start that says 57 Years Apart.")
    done = [data for name, data in events if name == "tool_done"]
    assert not done[0]["ok"] and "ND-09" in done[0]["error"]
    assert done[1]["ok"]


def test_a_hook_copies_the_moment_to_the_front_and_keeps_the_cut():
    from editor.ops import apply_ops
    from editor.timeline import Timeline
    from understanding.mud import MUD

    timeline = Timeline.model_validate({
        "fps": 30, "assets": {"a": {"id": "a", "kind": "video", "key": "k", "frames": 900}},
        "tracks": [
            {"id": "v1", "kind": "video", "items": [
                {"type": "clip", "id": "c1", "at": 0, "asset": "a", "src_in": 0, "src_out": 300},
                {"type": "clip", "id": "c2", "at": 300, "asset": "a", "src_in": 450, "src_out": 750,
                 "keyframes": {"scale": [{"f": 0, "v": 1}, {"f": 30, "v": 1.2}]}},
            ]},
            {"id": "t1", "kind": "text", "items": [{"type": "text", "id": "title", "at": 0, "text": "Hi", "style": "title", "dur": 60}]},
            {"id": "a1", "kind": "audio", "items": [{"type": "sfx", "id": "s1", "at": 320, "name": "pop", "dur": 9}]},
        ],
    })
    # The moment: 11.0–13.0 s on the timeline, 16.0–18.0 s into the footage of c2; its words run 15.9–18.1 s.
    mud = MUD.model_validate({"asset_id": "a", "kind": "video", "duration": 30.0, "words": [
        {"i": 0, "t0": 15.9, "t1": 16.3, "text": "Will"}, {"i": 1, "t0": 16.5, "t1": 18.1, "text": "you?"}]})
    ops = studio.hook_ops(timeline, {"a": mud}, 11.0, 13.0)
    after = apply_ops(timeline, ops)
    main = {i.id: i for i in after.tracks[0].items}
    hook = next(i for i in main.values() if i.id.startswith("hook-"))
    # Whole words: from "Will" (15.9 s) to just past "you?" (18.1 s), at the very front.
    assert (hook.at, hook.src_in, hook.src_out) == (0, 477, 545)
    # The cut stays as it was, later by the hook's length, its zoom intact.
    assert (main["c1"].at, main["c2"].at) == (68, 368) and main["c2"].keyframes["scale"][1].v == 1.2
    assert after.tracks[1].items[0].at == 0 and after.tracks[2].items[0].at == 320 + 68
