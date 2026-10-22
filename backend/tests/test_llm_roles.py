from __future__ import annotations

from typing import Any, get_args

import httpx
import pytest
from anthropic.types import Message
from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, ToolBox
from clients.ai import roles
from clients.ai.anthropic import Anthropic
from clients.ai.base import BaseAI, ToolReply, ToolSpec
from clients.ai.openai import OpenAI
from clients.ai.roles import (
    PROFILES, ROLE_EFFORT, ROLES, Role, call_with_fallback, get_role_client, is_transient, model_for_role,
)
from core.config import get_settings
from usage.pricing import token_cost
from usage.recorder import record_llm_call


@pytest.fixture
def settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROFILE", "openai")
    monkeypatch.setattr(settings, "LLM_ROLE_MODELS", {})
    monkeypatch.setattr(settings, "LLM_FALLBACK", ["openai", "anthropic"])
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4.1-mini")
    return settings


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    confidence: float


class Trim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: str
    frames: int = Field(ge=1)


def test_every_role_has_a_description_an_effort_and_a_model_in_every_profile():
    assert set(get_args(Role)) == set(ROLES) == set(ROLE_EFFORT)
    assert all(set(profile) == set(ROLES) for profile in PROFILES.values())


class TestModelForRole:
    def test_openai_profile_runs_every_role_on_the_configured_model(self, settings):
        for role in ROLES:
            choice = model_for_role(role)
            assert (choice.provider, choice.model) == ("openai", "gpt-4.1-mini"), role

    def test_the_studio_pick_moves_every_role_to_that_model_and_effort(self, settings):
        settings.LLM_PROFILE = "mixed"
        with roles.picked_model("gpt-5.6-sol-1", "xhigh"):
            director = model_for_role("director")
            router = model_for_role("router")
        assert (director.provider, director.model, director.effort) == ("openai", "gpt-5.6-sol-1", "xhigh")
        # Routing keeps its own effort: it classifies.
        assert (router.model, router.effort) == ("gpt-5.6-sol-1", "minimal")
        assert model_for_role("director").provider == "anthropic"

    def test_picking_only_an_effort_keeps_the_configured_model(self, settings):
        with roles.picked_model(None, "low"):
            choice = model_for_role("critic")
        assert (choice.model, choice.effort) == ("gpt-4.1-mini", "low")

    def test_the_configured_model_is_offered_first(self, settings, monkeypatch):
        monkeypatch.setattr(settings, "OPENAI_MODELS", ["gpt-5.6-sol-1", "gpt-4.1-mini"])
        assert roles.selectable_models() == ["gpt-4.1-mini", "gpt-5.6-sol-1"]

    def test_anthropic_profile_sizes_the_model_to_the_role(self, settings):
        settings.LLM_PROFILE = "anthropic"
        assert model_for_role("router").model == "claude-haiku-4-5"
        assert model_for_role("specialist").model == "claude-sonnet-5-5"
        director = model_for_role("director")
        assert (director.model, director.effort) == ("claude-opus-5-5", "medium")

    def test_mixed_profile_puts_only_judgement_on_opus(self, settings):
        settings.LLM_PROFILE = "mixed"
        assert {r for r in ROLES if model_for_role(r).provider == "anthropic"} == {"director", "critic", "judge"}

    def test_a_role_pin_beats_the_profile(self, settings):
        settings.LLM_ROLE_MODELS = {"director": "anthropic:claude-opus-5-5"}
        assert model_for_role("director").model == "claude-opus-5-5"
        assert model_for_role("router").provider == "openai"

    def test_overrides_apply_in_order(self, settings):
        assert model_for_role("director", plan_override="openai:gpt-5").model == "gpt-5"
        settings.LLM_ROLE_MODELS = {"director": "openai:gpt-4.1"}
        assert model_for_role("director", plan_override="openai:gpt-5").model == "gpt-4.1"
        assert model_for_role("director", plan_override="openai:gpt-5",
                              request_override="anthropic:claude-sonnet-5-5").model == "claude-sonnet-5-5"

    def test_a_bare_provider_pin_uses_its_configured_model(self, settings):
        assert model_for_role("router", request_override="openai").model == "gpt-4.1-mini"

    def test_no_effort_means_the_least_the_provider_allows(self, settings):
        assert model_for_role("router").effort == "minimal"
        assert model_for_role("router", request_override="anthropic:claude-opus-5-5").effort == "low"

    @pytest.mark.parametrize("pin", ["foo:bar", "gemini:gemini-3", ":gpt-4.1"])
    def test_an_unknown_provider_raises(self, settings, pin):
        with pytest.raises(ValueError, match="Unknown provider"):
            model_for_role("director", request_override=pin)

    def test_an_unknown_role_raises(self, settings):
        with pytest.raises(ValueError, match="Unknown role"):
            model_for_role("editor")


class FakeAI(BaseAI):
    """Records what was built and fails the way it is told to."""

    built: list[FakeAI] = []

    def __init__(self, provider: str, model: str, effort: str | None, error: Exception | None = None) -> None:
        self.provider, self.model, self.effort, self.error = provider, model, effort, error
        self.calls = 0
        self.closed = False
        FakeAI.built.append(self)

    async def chat(self, messages, **kwargs) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return f"{self.provider}:{self.model}"

    async def stream_chat(self, messages, **kwargs): raise NotImplementedError

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_registry(monkeypatch, settings):
    """Clients are FakeAI; ``errors`` maps a provider to what its calls raise, ``keys`` lists the configured ones."""
    FakeAI.built = []
    state: dict[str, Any] = {"errors": {}, "keys": {"openai", "anthropic"}}
    monkeypatch.setattr(roles, "_build", lambda c: FakeAI(c.provider, c.model, c.effort, state["errors"].get(c.provider)))
    monkeypatch.setattr(roles, "_has_key", lambda provider: provider in state["keys"])
    return state


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example/chat/completions")
    return httpx.HTTPStatusError("error", request=request, response=httpx.Response(status, request=request))


class TestGetRoleClient:
    def test_carries_the_role_and_its_defaults(self, fake_registry):
        client = get_role_client("router")
        assert isinstance(client, FakeAI)
        assert (client.role, client.temperature, client.model, client.effort) == ("router", 0.0, "gpt-4.1-mini", "minimal")
        assert get_role_client("director").temperature is None

    def test_a_provider_without_a_key_gives_way(self, fake_registry):
        fake_registry["keys"] = {"anthropic"}
        client = get_role_client("director")
        assert (client.provider, client.model) == ("anthropic", "claude-opus-5-5")


@pytest.mark.asyncio
class TestFallback:
    async def test_a_rate_limit_moves_to_the_next_provider_once(self, fake_registry):
        fake_registry["errors"] = {"openai": _status_error(429)}
        answer = await call_with_fallback("director", lambda client: client.chat([]))
        first, second = FakeAI.built
        assert answer == "anthropic:claude-opus-5-5"
        assert (first.calls, second.calls) == (1, 1) and first.closed and second.closed

    async def test_a_validation_error_is_never_retried_elsewhere(self, fake_registry):
        fake_registry["errors"] = {"openai": _status_error(400)}
        with pytest.raises(httpx.HTTPStatusError):
            await call_with_fallback("director", lambda client: client.chat([]))
        assert len(FakeAI.built) == 1

    async def test_the_last_provider_failing_raises(self, fake_registry):
        fake_registry["errors"] = {"openai": _status_error(503), "anthropic": httpx.ReadTimeout("slow")}
        with pytest.raises(httpx.ReadTimeout):
            await call_with_fallback("router", lambda client: client.chat([]))
        assert [c.provider for c in FakeAI.built] == ["openai", "anthropic"]

    async def test_keyless_providers_are_skipped(self, fake_registry):
        fake_registry["keys"] = {"openai"}
        fake_registry["errors"] = {"openai": _status_error(429)}
        with pytest.raises(httpx.HTTPStatusError):
            await call_with_fallback("router", lambda client: client.chat([]))
        assert len(FakeAI.built) == 1

    async def test_transient_errors(self):
        assert is_transient(_status_error(429)) and is_transient(_status_error(502))
        assert is_transient(httpx.ConnectError("down")) and is_transient(TimeoutError())
        assert not is_transient(_status_error(422)) and not is_transient(ValueError("bad"))


class TestEffortAndTemperature:
    def test_gpt_4_1_mini_gets_no_reasoning_effort_but_keeps_the_temperature(self):
        client = OpenAI(api_key="test", model="gpt-4.1-mini", effort="high")
        client.temperature = 0.0
        payload = client._build_payload([], stream=False, reasoning_effort="high")
        assert "reasoning_effort" not in payload and payload["temperature"] == 0.0

    def test_a_reasoning_model_gets_the_role_effort_and_no_temperature(self):
        client = OpenAI(api_key="test", model="gpt-5", effort="minimal")
        client.temperature = 0.0
        payload = client._build_payload([], stream=False)
        assert payload["reasoning_effort"] == "minimal" and "temperature" not in payload

    @pytest.mark.asyncio
    async def test_opus_payload_has_effort_and_no_temperature(self, monkeypatch):
        sent = await _anthropic_request(monkeypatch, "claude-opus-5-5", temperature=0.0)
        assert "temperature" not in sent and sent["output_config"]["effort"] == "low"

    @pytest.mark.asyncio
    async def test_haiku_payload_has_temperature_and_no_effort(self, monkeypatch):
        sent = await _anthropic_request(monkeypatch, "claude-haiku-4-5", temperature=0.0)
        assert sent["temperature"] == 0.0 and "output_config" not in sent and sent["max_tokens"] == 4096


def _message(content: list[dict], stop_reason: str = "end_turn", model: str = "claude-opus-5-5") -> Message:
    return Message.model_validate({
        "id": "msg_1", "type": "message", "role": "assistant", "model": model, "stop_reason": stop_reason,
        "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 5}, "content": content,
    })


def _capture_anthropic(monkeypatch, client: Anthropic, reply: Message) -> dict:
    sent: dict = {}

    async def fake_send(request, effort):
        sent.update(request)
        return reply

    monkeypatch.setattr(client, "_send", fake_send)
    return sent


async def _anthropic_request(monkeypatch, model: str, temperature: float | None) -> dict:
    client = Anthropic(api_key="test", model=model, effort="low")
    client.temperature = temperature
    sent = _capture_anthropic(monkeypatch, client, _message([{"type": "text", "text": "ok"}], model=model))
    await client.chat([{"role": "user", "content": "hi"}])
    return sent


def _openai_reply(message: dict, finish_reason: str = "stop") -> dict:
    return {"model": "gpt-4.1-mini", "usage": {}, "choices": [{"finish_reason": finish_reason, "message": message}]}


def _capture_openai(monkeypatch, client: OpenAI, reply: dict) -> dict:
    sent: dict = {}

    async def fake_create(messages, *, mode, **kwargs):
        sent.update(kwargs)
        return reply

    monkeypatch.setattr(client, "_create", fake_create)
    return sent


@pytest.mark.asyncio
class TestStructuredOutput:
    async def test_openai_sends_a_strict_json_schema(self, monkeypatch):
        client = OpenAI(api_key="test", model="gpt-4.1-mini")
        sent = _capture_openai(monkeypatch, client, _openai_reply({"content": '{"kind": "micro", "confidence": 0.9}'}))
        verdict = await client.chat_json([{"role": "user", "content": "route"}], Verdict)
        assert verdict == Verdict(kind="micro", confidence=0.9)
        assert sent["response_format"]["type"] == "json_schema" and sent["response_format"]["json_schema"]["strict"]
        assert sent["response_format"]["json_schema"]["schema"] == Verdict.model_json_schema()

    async def test_anthropic_sends_output_config_format(self, monkeypatch):
        client = Anthropic(api_key="test", model="claude-opus-5-5", effort="low")
        sent = _capture_anthropic(monkeypatch, client, _message([{"type": "text", "text": '{"kind": "plan", "confidence": 0.4}'}]))
        verdict = await client.chat_json([{"role": "user", "content": "route"}], Verdict)
        assert verdict.kind == "plan"
        assert sent["output_config"]["format"] == {"type": "json_schema", "schema": Verdict.model_json_schema()}

    async def test_a_reply_that_breaks_the_schema_raises(self, monkeypatch):
        client = OpenAI(api_key="test", model="gpt-4.1-mini")
        _capture_openai(monkeypatch, client, _openai_reply({"content": '{"kind": "micro"}'}))
        with pytest.raises(ValueError):
            await client.chat_json([{"role": "user", "content": "route"}], Verdict)


@pytest.mark.asyncio
class TestToolParity:
    async def test_openai_tools_are_strict_when_their_schema_allows(self, monkeypatch):
        class Loose(BaseModel):
            note: str = ""

        client = OpenAI(api_key="test", model="gpt-4.1-mini")
        sent = _capture_openai(monkeypatch, client, _openai_reply({"content": "done"}))
        await client.chat_with_tools([{"role": "user", "content": "trim"}], [
            ToolSpec("trim_item", "Trim.", Trim.model_json_schema()), ToolSpec("note", "Note.", Loose.model_json_schema())])
        strict, loose = (tool["function"] for tool in sent["tools"])
        assert strict["strict"] is True and "strict" not in loose

    async def test_a_cut_off_half_tool_call_is_marked_truncated(self, monkeypatch):
        client = OpenAI(api_key="test", model="gpt-4.1-mini")
        half = {"content": None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "trim_item", "arguments": '{"item": "c1", "fra'}}]}
        _capture_openai(monkeypatch, client, _openai_reply(half, finish_reason="length"))
        reply = await client.chat_with_tools([{"role": "user", "content": "trim"}], [])
        assert reply.truncated and reply.calls[0].arguments == {}

    async def test_openai_refusal_is_flagged(self, monkeypatch):
        client = OpenAI(api_key="test", model="gpt-4.1-mini")
        _capture_openai(monkeypatch, client, _openai_reply({"content": None, "refusal": "I can't help with that."}))
        reply = await client.chat_with_tools([{"role": "user", "content": "x"}], [])
        assert reply.refused and reply.text == "I can't help with that."

    async def test_anthropic_refusal_is_flagged_not_raised(self, monkeypatch):
        client = Anthropic(api_key="test", model="claude-opus-5-5", effort="low")
        _capture_anthropic(monkeypatch, client, _message([], stop_reason="refusal"))
        reply = await client.chat_with_tools([{"role": "user", "content": "x"}], [])
        assert reply.refused and not reply.calls

    async def test_the_agent_loop_stops_on_a_refusal_without_running_tools(self):
        ran: list[str] = []

        async def trim(project, args):
            ran.append(args.item)
            return "ok"

        class Refuses(FakeAI):
            async def chat_with_tools(self, messages, tools, *, max_tokens=4096) -> ToolReply:
                from clients.ai.base import ToolCall
                return ToolReply(text="", calls=[ToolCall("1", "trim_item", {"item": "c1", "frames": 1})], refused=True)

        box = ToolBox([AgentTool("trim_item", "Trim.", Trim, trim)])
        events = [e async for e in run_turn(Refuses("anthropic", "m", None), [], box, {}, TurnLimits(4, 30, 1.0))]
        assert events[-1].data["reason"] == "refused" and not ran


def test_dotted_tool_names_are_rejected():
    async def run(context, args): return "ok"

    with pytest.raises(ValueError, match="no dots"):
        ToolBox([AgentTool("timeline.trim", "Trim.", Trim, run)])


class TestMetering:
    @pytest.mark.parametrize(("provider", "model", "price_in", "price_out"), [
        ("openai", "gpt-4.1-mini", 0.40, 1.60), ("openai", "gpt-4.1", 2.00, 8.00), ("openai", "gpt-5", 1.25, 10.00),
        ("anthropic", "claude-opus-5-5", 4.00, 20.00), ("anthropic", "claude-sonnet-5-5", 2.00, 10.00),
        ("anthropic", "claude-haiku-4-5", 1.00, 5.00),
    ])
    def test_cost_is_tokens_times_price(self, provider, model, price_in, price_out):
        assert token_cost(provider, model, 12_000, 3_000) == pytest.approx((12_000 * price_in + 3_000 * price_out) / 1e6)

    @pytest.mark.asyncio
    async def test_a_role_call_is_costed(self):
        cost = await record_llm_call("openai", "gpt-4.1", input_tokens=1_000_000, role="director")
        assert cost == pytest.approx(2.0)


class TestOwnAnthropicKey:
    def test_a_turn_on_a_persons_own_key_runs_every_role_on_claude_and_never_falls_back(self, settings):
        from clients.ai.roles import OWN_KEY_MODELS, _chain, get_role_client, model_for_role, own_anthropic_key, picked_model

        with own_anthropic_key("sk-ant-test-0123456789abcdef"), picked_model("claude-opus-5-5", None):
            for role in ("studio", "router", "director"):
                assert (model_for_role(role).provider, model_for_role(role).model) == ("anthropic", "claude-opus-5-5")
            assert len(_chain("studio", model_for_role("studio"))) == 1
            client = get_role_client("studio")
            assert client.api_key == "sk-ant-test-0123456789abcdef" and client.model == "claude-opus-5-5"
        with own_anthropic_key("sk-ant-test-0123456789abcdef"):
            assert model_for_role("studio").model == OWN_KEY_MODELS[0]
        # Outside the turn, nothing of the key is left.
        assert model_for_role("studio").provider != "anthropic" or settings.LLM_PROFILE == "anthropic"

    def test_the_agent_route_takes_only_an_anthropic_key_and_its_claude_models(self):
        import pytest

        from core.exceptions import CustomException
        from editor.route import _check_model, _own_key

        assert _own_key(None) is None
        assert _own_key("  sk-ant-api03-abcdefghijklmnop  ") == "sk-ant-api03-abcdefghijklmnop"
        with pytest.raises(CustomException):
            _own_key("not-a-key")
        _check_model("claude-sonnet-5-5", own_key=True)
        with pytest.raises(CustomException):
            _check_model("claude-sonnet-5-5")
