"""The studio agent (brain/studio.py) against a real Postgres, with a scripted model.

Skipped unless TEST_DATABASE_URL points at a disposable database (see test_editor_db.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from brain import studio
from brain.schema import AgentRequest
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


@pytest.fixture(autouse=True)
def fixed_turn_id(monkeypatch):
    monkeypatch.setattr(studio, "uuid4", lambda: SimpleNamespace(hex=TURN.removeprefix("studio-") + "ffff"))


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

    async def fake_grab(asset, seconds, label, s3=None) -> bytes:
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
