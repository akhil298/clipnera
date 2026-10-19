from __future__ import annotations

import json

import pytest

from clients.ai import TEXT_PROVIDERS, get_text_client
from clients.ai.base import ToolResult, ToolSpec
from clients.ai.anthropic import THINKING_ALLOWANCE_BY_EFFORT, THINKING_TOKEN_ALLOWANCE, Anthropic
from clients.ai.groq import DEFAULT_MODEL as GROQ_DEFAULT_MODEL
from clients.ai.groq import MODEL_PROFILES, Groq
from clients.ai.openai import OpenAI, _base_url, _priced_model
from content_intelligence.classifier import CLASSIFICATION_JSON_SCHEMA, CONTENT_TAXONOMY
from content_intelligence.highlighter import MOMENTS_JSON_SCHEMA
from content_intelligence.metadata_gen import METADATA_JSON_SCHEMA
from content_intelligence.research import RESEARCH_JSON_SCHEMA

# Decommissioned 2026-08-16 and moved to Enterprise-only; a developer key
# cannot call either, so neither may reappear as a default or a profile.
RETIRED_GROQ_MODELS = ("llama-3.1-8b-instant", "llama-3.3-70b-versatile")


class _FakeMessage:
    """Minimal stand-in for an SDK message, for shaping assertions."""

    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.stop_reason = stop_reason
        self.usage = type("Usage", (), {
            "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
        })()
        self.content = [type("Block", (), {"type": "text", "text": text})()]


class _FakeStream:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self._text = text
        self._stop_reason = stop_reason

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get_final_message(self):
        return _FakeMessage(self._text, self._stop_reason)


def _capturing_anthropic(
    reply: str = '{"ok": true}', stop_reason: str = "end_turn",
) -> tuple[Anthropic, dict]:
    """An Anthropic client whose outgoing request is captured, not sent."""
    client = Anthropic()
    captured: dict = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return _FakeStream(reply, stop_reason)

    client._client.messages.stream = fake_stream
    return client, captured


class TestProviderSelection:
    def test_every_text_provider_is_registered(self):
        assert set(TEXT_PROVIDERS) == {"groq", "anthropic", "openai"}

    def test_explicit_provider_wins(self):
        assert isinstance(get_text_client("groq"), Groq)
        assert isinstance(get_text_client("anthropic"), Anthropic)
        assert isinstance(get_text_client("openai"), OpenAI)

    def test_provider_name_is_case_and_space_insensitive(self):
        assert isinstance(get_text_client("  AnThRoPiC "), Anthropic)

    def test_unknown_provider_falls_back_rather_than_raising(self):
        # A typo in AI_PROVIDER must not take the whole pipeline down.
        assert isinstance(get_text_client("gpt4"), Groq)


class TestSharedClientContract:
    """Every client must satisfy what the content-intelligence steps call."""

    @pytest.mark.parametrize("factory", [Groq, Anthropic, OpenAI])
    def test_exposes_a_token_budget(self, factory):
        budget = factory().input_token_budget(2600)
        assert isinstance(budget, int)
        assert budget > 0

    @pytest.mark.parametrize("factory", [Groq, Anthropic, OpenAI])
    def test_has_the_methods_callers_use(self, factory):
        client = factory()
        assert callable(client.chat)
        assert callable(client.close)
        assert isinstance(client.model, str) and client.model

    def test_anthropic_offers_a_far_larger_window(self):
        # The reason to switch: a transcript Groq must split fits in one request.
        assert Anthropic().input_token_budget(2600) > Groq().input_token_budget(2600) * 10


class TestAnthropicRequestShape:
    def test_system_messages_are_lifted_out_of_the_conversation(self):
        system, conversation = Anthropic._split_system([
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ])
        assert system == "be terse"
        assert conversation == [{"role": "user", "content": "hi"}]

    def test_multiple_system_messages_are_joined(self):
        system, conversation = Anthropic._split_system([
            {"role": "system", "content": "one"},
            {"role": "system", "content": "two"},
            {"role": "user", "content": "hi"},
        ])
        assert system == "one\n\ntwo"
        assert len(conversation) == 1

    @pytest.mark.asyncio
    async def test_sampling_parameters_are_dropped_not_forwarded(self):
        # Current Claude models reject temperature with a 400, and every caller
        # in this codebase passes it because they were written against Groq.
        client, captured = _capturing_anthropic()
        await client.chat(
            [{"role": "user", "content": "hi"}],
            temperature=0.2, top_p=0.9, max_tokens=500,
        )
        assert "temperature" not in captured
        assert "top_p" not in captured

    @pytest.mark.asyncio
    async def test_output_cap_leaves_room_for_thinking(self):
        # Claude's thinking is billed against max_tokens. Sending the caller's
        # Groq-sized cap as-is let a 2600-token highlight call spend all of it
        # thinking and return no text, dropping the run to the heuristic.
        client, captured = _capturing_anthropic()
        await client.chat([{"role": "user", "content": "hi"}], max_tokens=500)
        # The room scales with the client's effort, which comes from settings.
        assert captured["max_tokens"] == 500 + THINKING_ALLOWANCE_BY_EFFORT.get(client.effort, THINKING_TOKEN_ALLOWANCE)

    @pytest.mark.asyncio
    async def test_json_schema_becomes_an_enforced_output_format(self):
        client, captured = _capturing_anthropic('{"moments": []}')
        await client.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=500, json_mode=True, json_schema=MOMENTS_JSON_SCHEMA,
        )
        assert captured["output_config"]["format"]["type"] == "json_schema"
        sent = captured["output_config"]["format"]["schema"]
        # Sanitized, not the constant itself: the API rejects numeric range
        # keywords, so they are stripped on the way out while the shared
        # constant keeps them for the providers and tests that want them.
        assert sent["properties"]["moments"]["items"]["required"] ==             MOMENTS_JSON_SCHEMA["properties"]["moments"]["items"]["required"]
        assert captured["output_config"]["effort"]

    @pytest.mark.asyncio
    async def test_range_keywords_are_stripped_from_the_sent_schema(self):
        # The API answers 400 "For 'number' type, properties maximum, minimum
        # are not supported", which used to fail the call and silently drop the
        # step to its heuristic fallback.
        client, captured = _capturing_anthropic('{"moments": []}')
        await client.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=500, json_mode=True, json_schema=MOMENTS_JSON_SCHEMA,
        )
        score = captured["output_config"]["format"]["schema"]["properties"]["moments"]["items"]["properties"]["score"]
        assert "minimum" not in score and "maximum" not in score
        # The bound still reaches the model, as prose the API accepts.
        assert "minimum: 0" in score["description"]
        assert "maximum: 1" in score["description"]
        # The shared constant is not mutated.
        assert MOMENTS_JSON_SCHEMA["properties"]["moments"]["items"]["properties"]["score"]["maximum"] == 1

    @pytest.mark.asyncio
    async def test_classification_schema_survives_sanitizing(self):
        client, captured = _capturing_anthropic('{"category": "tech"}')
        await client.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=300, json_mode=True, json_schema=CLASSIFICATION_JSON_SCHEMA,
        )
        sent = captured["output_config"]["format"]["schema"]
        assert "minimum" not in sent["properties"]["confidence"]
        # The enum is supported and must survive untouched.
        assert sent["properties"]["category"]["enum"] == list(CONTENT_TAXONOMY)
        assert sent["required"] == CLASSIFICATION_JSON_SCHEMA["required"]

    @pytest.mark.asyncio
    async def test_system_prompt_is_cached(self):
        # The instruction block repeats on every call of a step; caching it is
        # the difference between paying full price per clip and a tenth of it.
        client, captured = _capturing_anthropic()
        await client.chat([
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ], max_tokens=500)
        assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_empty_reply_raises_instead_of_returning_blank(self):
        client, _ = _capturing_anthropic("   ")
        with pytest.raises(RuntimeError, match="no text content"):
            await client.chat([{"role": "user", "content": "hi"}], max_tokens=500)

    @pytest.mark.asyncio
    async def test_empty_reply_at_the_cap_names_thinking_as_the_cause(self):
        client, _ = _capturing_anthropic("", stop_reason="max_tokens")
        with pytest.raises(RuntimeError, match="spent on thinking"):
            await client.chat([{"role": "user", "content": "hi"}], max_tokens=500)


class _FakeResponse:
    is_error = False

    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


def _capturing_openai(message: dict, finish_reason: str = "stop") -> tuple[OpenAI, dict]:
    """An OpenAI client whose outgoing request is captured, not sent."""
    client = OpenAI(api_key="test", model="my-deployment")
    captured: dict = {}

    async def fake_post(path, json):
        captured.update(json, path=path)
        return _FakeResponse({
            "model": "gpt-4.1-mini-2025-04-14",
            "choices": [{"message": message, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        })

    client._client.post = fake_post
    return client, captured


class TestOpenAIRequestShape:
    @pytest.mark.asyncio
    async def test_callers_arguments_become_an_openai_request(self):
        client, captured = _capturing_openai({"content": '{"moments": []}'})
        reply = await client.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=500, temperature=0.2, json_mode=True, json_schema=MOMENTS_JSON_SCHEMA,
        )
        assert reply == '{"moments": []}'
        assert captured["path"] == "chat/completions"
        assert captured["model"] == "my-deployment"
        assert captured["max_completion_tokens"] == 500
        # A strict-ready schema is enforced, so an enum can only come back as one of its values.
        assert captured["response_format"] == {
            "type": "json_schema", "json_schema": {"name": "reply", "schema": MOMENTS_JSON_SCHEMA, "strict": True},
        }
        # Neither is an API parameter here; forwarding either fails the request.
        assert "max_tokens" not in captured and "json_schema" not in captured and "json_mode" not in captured

    @pytest.mark.asyncio
    async def test_a_loose_schema_falls_back_to_json_mode(self):
        client, captured = _capturing_openai({"content": "{}"})
        loose = {"type": "object", "properties": {"a": {"type": "string"}}}
        await client.chat([{"role": "user", "content": "hi"}], json_mode=True, json_schema=loose)
        assert captured["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_a_deployment_refusing_schemas_is_retried_in_json_mode(self):
        import httpx

        client = OpenAI(api_key="test", model="old-deployment")
        formats: list[dict] = []

        async def fake_post(path, json):
            formats.append(json["response_format"])
            if json["response_format"]["type"] == "json_schema":
                request = httpx.Request("POST", "https://x/chat/completions")
                return httpx.Response(400, request=request, text="response_format json_schema unsupported")
            return _FakeResponse({"model": "m", "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})

        client._client.post = fake_post
        assert await client.chat([{"role": "user", "content": "hi"}], json_mode=True, json_schema=MOMENTS_JSON_SCHEMA) == "{}"
        assert [f["type"] for f in formats] == ["json_schema", "json_object"]

    @pytest.mark.asyncio
    async def test_empty_reply_raises_instead_of_returning_blank(self):
        client, _ = _capturing_openai({"content": "  "}, finish_reason="length")
        with pytest.raises(RuntimeError, match="no content"):
            await client.chat([{"role": "user", "content": "hi"}], max_tokens=500)

    @pytest.mark.asyncio
    async def test_tool_calls_are_parsed_and_echoed_back_unchanged(self):
        raw = [{"id": "call_1", "type": "function", "function": {"name": "trim", "arguments": '{"clip_id": "c1"}'}}]
        client, captured = _capturing_openai({"content": None, "tool_calls": raw}, finish_reason="tool_calls")
        reply = await client.chat_with_tools(
            [{"role": "user", "content": "trim c1"}],
            [ToolSpec("trim", "Trim a clip", {"type": "object", "properties": {}})],
        )
        assert captured["tools"][0]["function"]["name"] == "trim"
        assert [(c.id, c.name, c.arguments) for c in reply.calls] == [("call_1", "trim", {"clip_id": "c1"})]
        assert reply.message == {"role": "assistant", "content": "", "tool_calls": raw}
        assert client.tool_results([ToolResult("call_1", "bad", is_error=True)]) == [
            {"role": "tool", "tool_call_id": "call_1", "content": "Error: bad"},
        ]

    def test_a_call_is_priced_at_the_model_that_served_it(self):
        # An Azure deployment name is arbitrary; the served model is what has a price.
        assert _priced_model("gpt-4.1-mini-2025-04-14", "my-deployment") == "gpt-4.1-mini"
        assert _priced_model(None, "gpt-4o-mini") == "gpt-4o-mini"

    @pytest.mark.parametrize("endpoint,expected", [
        ("", "https://api.openai.com/v1/"),
        ("https://proxy.example.com/v1/", "https://proxy.example.com/v1/"),
        ("https://res.services.ai.azure.com/api/projects/p", "https://res.services.ai.azure.com/api/projects/p/openai/v1/"),
        ("https://res.openai.azure.com/openai/v1/", "https://res.openai.azure.com/openai/v1/"),
    ])
    def test_endpoint_is_accepted_as_copied_from_the_portal(self, monkeypatch, endpoint, expected):
        import clients.ai.openai as openai_module

        monkeypatch.setattr(openai_module.settings, "OPENAI_ENDPOINT", endpoint)
        assert _base_url() == expected


class TestGroqIgnoresAnthropicOnlyArguments:
    @pytest.mark.asyncio
    async def test_json_schema_is_not_forwarded_to_groq(self):
        # Groq has no schema-constrained output; forwarding it would be an
        # unknown API parameter and fail the request.
        client = Groq()
        captured: dict = {}

        async def fake_once(messages, json_mode=False, **kwargs):
            captured.update(kwargs)
            captured["json_mode"] = json_mode
            return '{"moments": []}'

        client._chat_once = fake_once
        await client.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=500, json_mode=True, json_schema=MOMENTS_JSON_SCHEMA,
        )
        assert "json_schema" not in captured
        assert captured["json_mode"] is True


class TestRetiredGroqModels:
    @pytest.mark.parametrize("model", RETIRED_GROQ_MODELS)
    def test_retired_models_are_not_profiled(self, model):
        assert model not in MODEL_PROFILES

    def test_default_model_is_callable_today(self):
        assert GROQ_DEFAULT_MODEL not in RETIRED_GROQ_MODELS
        assert GROQ_DEFAULT_MODEL in MODEL_PROFILES


class TestSchemas:
    """Every schema the pipeline parses must be strict enough to rely on."""

    @pytest.mark.parametrize(
        "schema",
        [MOMENTS_JSON_SCHEMA, RESEARCH_JSON_SCHEMA, CLASSIFICATION_JSON_SCHEMA, METADATA_JSON_SCHEMA],
    )
    def test_schema_is_closed_and_has_required_fields(self, schema):
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["required"]

    def test_category_enum_matches_the_taxonomy(self):
        # A category outside the taxonomy silently degrades framing, hashtags
        # and scoring, so the schema pins it to the same list the code uses.
        assert CLASSIFICATION_JSON_SCHEMA["properties"]["category"]["enum"] == list(CONTENT_TAXONOMY)

    def test_moment_scores_are_bounded_to_the_unit_interval(self):
        moment = MOMENTS_JSON_SCHEMA["properties"]["moments"]["items"]
        assert moment["properties"]["score"]["maximum"] == 1
        assert moment["additionalProperties"] is False
        for field in ("start_time", "end_time", "title", "score", "scores"):
            assert field in moment["required"]


class TestOpenAIReasoningEffort:
    """Only reasoning models get ``reasoning_effort``; others keep their request unchanged."""

    def _payload(self, model: str, **kwargs):
        from clients.ai.openai import OpenAI

        client = OpenAI.__new__(OpenAI)
        client.model = model
        return client._build_payload([{"role": "user", "content": "hi"}], stream=False, **kwargs)

    def test_non_reasoning_model_is_left_alone(self):
        payload = self._payload("gpt-4.1-mini", max_tokens=500, temperature=0.7)
        assert "reasoning_effort" not in payload
        assert payload["temperature"] == 0.7
        assert payload["max_completion_tokens"] == 500

    def test_reasoning_model_thinks_at_high_effort_with_room_to_answer(self):
        payload = self._payload("gpt-5-mini", max_tokens=500, temperature=0.7)
        assert payload["reasoning_effort"] == "high"
        assert "temperature" not in payload
        assert payload["max_completion_tokens"] > 500

    def test_later_families_are_reasoning_models_too(self):
        assert self._payload("gpt-6.1-sol-1")["reasoning_effort"] == "high"

    def test_chat_variant_gets_no_effort(self):
        assert "reasoning_effort" not in self._payload("gpt-5-chat-latest")


class TestOpenAIToolsOnResponses:
    """Deployments that refuse tools with reasoning on chat completions get them on the Responses API."""

    REFUSAL = {"error": {"message": "Function tools with reasoning_effort are not supported", "param": "reasoning_effort"}}
    TOOL = ToolSpec(name="clip_length", description="Length of a clip.",
                    schema={"type": "object", "additionalProperties": False, "required": ["item"],
                            "properties": {"item": {"type": "string"}}})

    @pytest.fixture
    def client(self, monkeypatch):
        import httpx

        import clients.ai.openai as openai_module

        async def no_record(*args, **kwargs):
            return None

        monkeypatch.setattr(openai_module, "record_llm_call", no_record)
        monkeypatch.setattr(openai_module, "_TOOLS_ON_RESPONSES", set())
        self.requests: list[tuple[str, dict]] = []

        def handle(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.requests.append((request.url.path.rsplit("/", 1)[-1], body))
            if request.url.path.endswith("chat/completions"):
                return httpx.Response(400, json=self.REFUSAL)
            return httpx.Response(200, json={
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "function_call", "call_id": "call_1", "name": "clip_length", "arguments": '{"item": "c1"}'},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            })

        client = OpenAI(api_key="test", model="gpt-6-astra-1", effort="high")
        client._client = httpx.AsyncClient(base_url="https://example.test/", transport=httpx.MockTransport(handle))
        return client

    @pytest.mark.asyncio
    async def test_a_refused_tool_call_moves_to_responses_and_stays_there(self, client):
        history = [
            {"role": "system", "content": "Edit."},
            {"role": "user", "content": "How long is c1?"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_0", "type": "function", "function": {"name": "clip_length", "arguments": '{"item": "c0"}'}}]},
            *client.tool_results([ToolResult(call_id="call_0", content="120 frames")]),
        ]
        reply = await client.chat_with_tools(history, [self.TOOL])
        await client.chat_with_tools(history, [self.TOOL])

        assert [path for path, _ in self.requests] == ["completions", "responses", "responses"]
        sent = self.requests[1][1]
        assert sent["reasoning"] == {"effort": "high"}
        assert [item.get("type") for item in sent["input"]] == [
            "message", "message", "function_call", "function_call_output"]
        assert sent["input"][3] == {"type": "function_call_output", "call_id": "call_0", "output": "120 frames"}
        assert [(c.name, c.arguments) for c in reply.calls] == [("clip_length", {"item": "c1"})]
        # The history stays in chat format, so the loop needs no changes.
        assert reply.message["tool_calls"][0]["function"]["name"] == "clip_length"


class TestOpenAIEffortFallback:
    """An effort a deployment refuses moves to the nearest one it takes."""

    def test_nearest_effort_goes_up_to_the_lightest_supported(self):
        from clients.ai.openai import _nearest_effort

        assert _nearest_effort("minimal", ("low", "medium", "high", "xhigh")) == "low"
        assert _nearest_effort("minimal", ("none", "low", "medium")) == "low"
        assert _nearest_effort("high", ("low", "high")) == "high"
        assert _nearest_effort("xhigh", ("low", "medium", "high")) == "high"

    def test_a_refusal_teaches_the_model_its_efforts(self, monkeypatch):
        import httpx

        import clients.ai.openai as openai_module
        from clients.ai.openai import _learn_efforts, reasoning_effort

        monkeypatch.setattr(openai_module, "_SUPPORTED_EFFORTS", {})
        refusal = httpx.Response(400, json={"error": {"param": "reasoning_effort", "message": (
            "Unsupported value: 'reasoning_effort' does not support 'minimal' with this model. "
            "Supported values are: 'low', 'medium', 'high', and 'xhigh'.")}},
            request=httpx.Request("POST", "https://example.test/chat/completions"))
        assert _learn_efforts("gpt-6-astra-1", httpx.HTTPStatusError("400", request=refusal.request, response=refusal))
        assert reasoning_effort("gpt-6-astra-1", "minimal") == "low"
        assert reasoning_effort("gpt-6-astra-1", "xhigh") == "xhigh"


class TestOpenAIKnownLimits:
    """Deployments listed in settings are handled right from their first call, with no refusal to learn from."""

    def test_astra_is_known_from_the_start(self):
        import clients.ai.openai as openai_module

        assert "gpt-6-astra-1" in openai_module._TOOLS_ON_RESPONSES
        assert openai_module._SUPPORTED_EFFORTS["gpt-6-astra-1"] == ("low", "medium", "high", "xhigh")

    def test_a_listed_model_never_asks_for_an_effort_it_refuses(self):
        from clients.ai.openai import reasoning_effort

        assert reasoning_effort("gpt-6-astra-1", "minimal") == "low"
        assert reasoning_effort("gpt-6-astra-1", "high") == "high"

    @pytest.mark.asyncio
    async def test_a_listed_model_sends_its_first_tool_call_to_responses(self, monkeypatch):
        import httpx

        import clients.ai.openai as openai_module

        async def no_record(*args, **kwargs):
            return None

        monkeypatch.setattr(openai_module, "record_llm_call", no_record)
        paths: list[str] = []

        def handle(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path.rsplit("/", 1)[-1])
            body = json.loads(request.content)
            assert body["reasoning"] == {"effort": "low"}
            return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "Done."}]}],
                                             "usage": {"input_tokens": 3, "output_tokens": 1}})

        client = OpenAI(api_key="test", model="gpt-6-astra-1", effort="minimal")
        client._client = httpx.AsyncClient(base_url="https://example.test/", transport=httpx.MockTransport(handle))
        reply = await client.chat_with_tools([{"role": "user", "content": "Hi"}], [TestOpenAIToolsOnResponses.TOOL])

        assert paths == ["responses"]
        assert reply.text == "Done."

    def test_unlisted_models_still_learn_from_a_refusal(self):
        import clients.ai.openai as openai_module

        assert "gpt-6.1-sol-1" not in openai_module._TOOLS_ON_RESPONSES
        assert openai_module.reasoning_effort("gpt-6.1-sol-1", "minimal") == "minimal"


def test_a_rate_limited_call_waits_as_long_as_the_api_asks():
    from types import SimpleNamespace

    import httpx

    from clients.ai.openai import MAX_RETRY_AFTER_SECONDS, _retry_wait

    def state(status: int, headers: dict[str, str], attempt: int = 1):
        response = httpx.Response(status, headers=headers, request=httpx.Request("POST", "https://x"))
        exc = httpx.HTTPStatusError("busy", request=response.request, response=response)
        return SimpleNamespace(attempt_number=attempt, outcome=SimpleNamespace(exception=lambda: exc))

    assert _retry_wait(state(429, {"retry-after": "23"})) == 23
    assert _retry_wait(state(429, {"retry-after-ms": "1500"})) == 1.5
    assert _retry_wait(state(429, {"retry-after": "600"})) == MAX_RETRY_AFTER_SECONDS
    assert _retry_wait(state(429, {}, attempt=2)) == 20
    assert _retry_wait(state(503, {}, attempt=3)) == 4
