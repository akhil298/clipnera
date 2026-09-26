from __future__ import annotations

import pytest

from clients.ai import TEXT_PROVIDERS, get_text_client
from clients.ai.anthropic import THINKING_ALLOWANCE_BY_EFFORT, THINKING_TOKEN_ALLOWANCE, Anthropic
from clients.ai.groq import DEFAULT_MODEL as GROQ_DEFAULT_MODEL
from clients.ai.groq import MODEL_PROFILES, Groq
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
    def test_both_providers_are_registered(self):
        assert set(TEXT_PROVIDERS) == {"groq", "anthropic"}

    def test_explicit_provider_wins(self):
        assert isinstance(get_text_client("groq"), Groq)
        assert isinstance(get_text_client("anthropic"), Anthropic)

    def test_provider_name_is_case_and_space_insensitive(self):
        assert isinstance(get_text_client("  AnThRoPiC "), Anthropic)

    def test_unknown_provider_falls_back_rather_than_raising(self):
        # A typo in AI_PROVIDER must not take the whole pipeline down.
        assert isinstance(get_text_client("gpt4"), Groq)


class TestSharedClientContract:
    """Both clients must satisfy what the content-intelligence steps call."""

    @pytest.mark.parametrize("factory", [Groq, Anthropic])
    def test_exposes_a_token_budget(self, factory):
        budget = factory().input_token_budget(2600)
        assert isinstance(budget, int)
        assert budget > 0

    @pytest.mark.parametrize("factory", [Groq, Anthropic])
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
