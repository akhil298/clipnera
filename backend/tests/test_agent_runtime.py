from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from anthropic.types import Message
from pydantic import BaseModel, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, Seen, ToolBox
from clients.ai.anthropic import Anthropic
from clients.ai.base import BaseAI, ToolCall, ToolReply, ToolResult, ToolSpec
from clients.ai.groq import Groq
from core.exceptions import CustomException
from usage.recorder import record_llm_call

pytestmark = pytest.mark.asyncio


class Trim(BaseModel):
    item: str
    frames: int = Field(ge=1)


async def trim(project: dict, args: Trim) -> dict:
    if args.item not in project:
        raise CustomException(message=f"There is no item {args.item}.", code="UNKNOWN_ITEM", status_code=422)
    project[args.item] -= args.frames
    return {"item": args.item, "frames": project[args.item]}


TOOLS = ToolBox([AgentTool("trim", "Shorten an item by some frames.", Trim, trim)])
LIMITS = TurnLimits(max_steps=4, seconds=30, usd=0.05)


class ScriptedModel(BaseAI):
    """Replies from a script, one per step, and bills each step like a Sonnet call."""

    def __init__(self, *replies: ToolReply, tokens_per_step: int = 1000) -> None:
        self.replies = list(replies)
        self.seen: list[list[dict[str, Any]]] = []
        self.tokens = tokens_per_step

    async def chat_with_tools(self, messages, tools, *, max_tokens=4096) -> ToolReply:
        self.seen.append(list(messages))
        await record_llm_call("anthropic", "claude-sonnet-5", input_tokens=self.tokens, output_tokens=self.tokens)
        return self.replies.pop(0)

    def tool_results(self, results: list[ToolResult]) -> list[dict[str, Any]]:
        return [{"role": "tool", "id": r.call_id, "content": r.content, "error": r.is_error} for r in results]

    async def chat(self, messages, **kwargs): raise NotImplementedError

    async def stream_chat(self, messages, **kwargs): raise NotImplementedError

    async def close(self) -> None: ...


def calls(*pairs: tuple[str, dict]) -> ToolReply:
    return ToolReply(text="", calls=[ToolCall(f"t{i}", name, args) for i, (name, args) in enumerate(pairs)],
                     message={"role": "assistant", "content": "calling"})


def answer(text: str) -> ToolReply:
    return ToolReply(text=text, message={"role": "assistant", "content": text})


async def collect(model: BaseAI, project: dict, messages: list | None = None, limits: TurnLimits = LIMITS) -> tuple[list, list]:
    messages = messages if messages is not None else [{"role": "user", "content": "tighten it"}]
    events = [event async for event in run_turn(model, messages, TOOLS, project, limits)]
    return events, messages


class TestToolBox:
    async def test_runs_a_valid_call(self) -> None:
        result = await TOOLS.call({"c1": 90}, ToolCall("1", "trim", {"item": "c1", "frames": 30}))
        assert (result.is_error, result.content) == (False, '{"item": "c1", "frames": 60}')

    async def test_bad_input_goes_back_to_the_model(self) -> None:
        result = await TOOLS.call({"c1": 90}, ToolCall("1", "trim", {"item": "c1", "frames": 0}))
        assert result.is_error and "frames" in result.content

    async def test_a_refused_edit_names_its_code(self) -> None:
        result = await TOOLS.call({}, ToolCall("1", "trim", {"item": "c9", "frames": 3}))
        assert result.is_error and result.content.startswith("UNKNOWN_ITEM: There is no item c9.")

    async def test_unknown_tools_are_errors_not_crashes(self) -> None:
        result = await TOOLS.call({}, ToolCall("1", "delete_everything", {}))
        assert result.is_error

    def test_specs_carry_the_input_schema(self) -> None:
        (spec,) = TOOLS.specs()
        assert spec.name == "trim" and spec.schema["required"] == ["item", "frames"]


class TestRunTurn:
    async def test_calls_tools_until_the_model_answers(self) -> None:
        project = {"c1": 90}
        model = ScriptedModel(calls(("trim", {"item": "c1", "frames": 30})), answer("Trimmed one second."))
        events, messages = await collect(model, project)
        assert project == {"c1": 60}
        assert [e.type for e in events] == ["tool_call", "tool_result", "text", "done"]
        assert events[-1].data["reason"] == "answered" and events[-1].data["steps"] == 2
        # The second step saw the first step's reply and its tool result.
        assert [m["role"] for m in model.seen[1]] == ["user", "assistant", "tool"]
        assert messages[-1] == {"role": "assistant", "content": "Trimmed one second."}

    async def test_a_failed_call_lets_the_model_fix_it(self) -> None:
        project = {"c1": 90}
        model = ScriptedModel(calls(("trim", {"item": "c9", "frames": 3})),
                              calls(("trim", {"item": "c1", "frames": 3})), answer("Done."))
        events, _ = await collect(model, project)
        results = [e.data["ok"] for e in events if e.type == "tool_result"]
        assert results == [False, True] and project == {"c1": 87}

    async def test_a_truncated_reply_runs_no_tools(self) -> None:
        project = {"c1": 90}
        cut = ToolReply(text="", calls=[ToolCall("t0", "trim", {"item": "c1"})], message={"role": "assistant"}, truncated=True)
        events, _ = await collect(ScriptedModel(cut, answer("Sorry.")), project)
        assert project == {"c1": 90}
        assert next(e for e in events if e.type == "tool_result").data["ok"] is False

    async def test_the_step_limit_ends_the_turn(self) -> None:
        loop = [calls(("trim", {"item": "c1", "frames": 1})) for _ in range(5)]
        events, _ = await collect(ScriptedModel(*loop), {"c1": 90}, limits=TurnLimits(max_steps=2, seconds=30, usd=1))
        assert events[-1].data == {"reason": "steps", "steps": 2, "cost_usd": pytest.approx(0.024)}

    async def test_the_dollar_cap_stops_before_the_next_call(self) -> None:
        # Each step bills 20k in + 20k out on Sonnet: $0.24, past a $0.10 cap after one step.
        loop = [calls(("trim", {"item": "c1", "frames": 1})) for _ in range(3)]
        model = ScriptedModel(*loop, tokens_per_step=20_000)
        events, _ = await collect(model, {"c1": 90}, limits=TurnLimits(max_steps=3, seconds=30, usd=0.10))
        assert events[-1].data["reason"] == "budget" and len(model.seen) == 1

    async def test_pictures_a_tool_saw_follow_its_result(self) -> None:
        async def look(_: dict, __: NoArgs) -> Seen:
            return Seen(text="0:01.00: clip c1", jpegs=[b"jpeg-1"])

        model = ScriptedModel(calls(("look", {})), answer("Looks fine."))
        tools = ToolBox([AgentTool("look", "See a frame.", NoArgs, look)])
        messages = [{"role": "user", "content": "check it"}]
        events = [event async for event in run_turn(model, messages, tools, {}, LIMITS)]
        assert [e.type for e in events] == ["tool_call", "tool_result", "text", "done"]
        assert events[1].data["content"] == "0:01.00: clip c1"
        # The second step saw the result, then the picture as a user message.
        tool_message, picture = model.seen[1][-2:]
        assert tool_message["content"] == "0:01.00: clip c1"
        assert picture["role"] == "user" and picture["content"][1]["type"] == "image_url"


class NoArgs(BaseModel):
    pass


class TestAnthropicTools:
    def test_tool_results_and_pictures_go_as_one_user_turn(self) -> None:
        client = Anthropic(api_key="test", model="claude-sonnet-5", effort="low")
        messages = [{"role": "system", "content": "Edit."}, {"role": "user", "content": "check it"},
                    {"role": "assistant", "content": [{"type": "tool_use", "id": "t0", "name": "look", "input": {}}]},
                    *client.tool_results([ToolResult("t0", "clip c1")]), client.image_message("Frames.", [b"jpeg"])]
        system, conversation = client._split_system(messages)
        assert system == "Edit." and [m["role"] for m in conversation] == ["user", "assistant", "user"]
        assert [block["type"] for block in conversation[-1]["content"]] == ["tool_result", "image", "text"]

    async def test_tool_use_and_thinking_blocks_round_trip(self, monkeypatch) -> None:
        client = Anthropic(api_key="test", model="claude-sonnet-5", effort="low")
        sent: dict = {}
        response = Message.model_validate({
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5",
            "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "content": [
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "text", "text": "Trimming."},
                {"type": "tool_use", "id": "toolu_1", "name": "trim", "input": {"item": "c1", "frames": 30}},
            ],
        })

        async def fake_send(request, effort):
            sent.update(request)
            return response

        monkeypatch.setattr(client, "_send", fake_send)
        reply = await client.chat_with_tools(
            [{"role": "system", "content": "You edit videos."}, {"role": "user", "content": "trim c1"}],
            [ToolSpec("trim", "Shorten an item.", Trim.model_json_schema())],
        )
        assert reply.text == "Trimming." and reply.calls == [ToolCall("toolu_1", "trim", {"item": "c1", "frames": 30})]
        assert [b["type"] for b in reply.message["content"]] == ["thinking", "text", "tool_use"]
        assert reply.message["content"][0]["signature"] == "sig"
        assert sent["tools"][-1]["cache_control"] == {"type": "ephemeral"}
        assert sent["system"][0]["text"] == "You edit videos." and "tool_choice" not in sent
        (results,) = client.tool_results([ToolResult("toolu_1", "ok"), ToolResult("toolu_2", "nope", is_error=True)])
        assert [r["tool_use_id"] for r in results["content"]] == ["toolu_1", "toolu_2"]


class TestGroqTools:
    async def test_function_calls_round_trip(self, monkeypatch) -> None:
        client = Groq(api_key="test", model="openai/gpt-oss-120b")
        call = SimpleNamespace(id="call_1", function=SimpleNamespace(name="trim", arguments='{"item": "c1", "frames": 30}'))
        response = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="tool_calls", message=SimpleNamespace(content=None, tool_calls=[call]))])
        sent: dict = {}

        async def fake_create(messages, *, mode, **kwargs):
            sent.update(kwargs)
            return response

        monkeypatch.setattr(client, "_create", fake_create)
        reply = await client.chat_with_tools([{"role": "user", "content": "trim c1"}],
                                             [ToolSpec("trim", "Shorten an item.", Trim.model_json_schema())])
        assert reply.calls == [ToolCall("call_1", "trim", {"item": "c1", "frames": 30})]
        assert reply.message["tool_calls"][0]["function"]["arguments"] == '{"item": "c1", "frames": 30}'
        assert sent["tools"][0]["function"]["name"] == "trim" and sent["tool_choice"] == "auto"
        assert client.tool_results([ToolResult("call_1", "bad", is_error=True)]) == [
            {"role": "tool", "tool_call_id": "call_1", "content": "Error: bad"}]
