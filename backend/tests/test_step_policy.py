from __future__ import annotations

import pytest

from clients.ai import STEP_MODELS, get_text_client, model_for_step, provider_for_tier
from clients.ai.anthropic import Anthropic
from clients.ai.groq import Groq
from clients.ai.openai import OpenAI
from content_intelligence.highlighter import MAX_CLIPS_PER_HOUR, MIN_CLIPS, HighlightDetector
from content_intelligence.metadata_gen import (
    METADATA_JSON_SCHEMA,
    TITLE_JSON_SCHEMA,
    MetadataGenerator,
)
from content_intelligence.service import ContentIntelligenceService

# Steps that stay on Groq whatever the user pays.
ALWAYS_FREE = ("classification",)
# Steps where Pro buys a stronger model.
FOLLOWS_TIER = ("topic_research", "highlight_detection", "titles", "map", "director")


class _Settings:
    AI_PROVIDER = "auto"
    GROQ_API_KEY = "x"
    ANTHROPIC_API_KEY = "x"
    OPENAI_API_KEY = "x"
    OPENAI_MODEL = "gpt-4.1-mini"
    ANTHROPIC_MODEL = "claude-opus-5"
    ANTHROPIC_EFFORT = "high"
    GROQ_MODEL = "openai/gpt-oss-20b"


@pytest.fixture
def auto_settings(monkeypatch):
    import clients.ai as ai

    settings = _Settings()
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    return settings


class TestStepPolicy:
    @pytest.mark.parametrize("step", ALWAYS_FREE)
    def test_cheap_steps_stay_on_groq_even_for_pro(self, auto_settings, step):
        assert provider_for_tier(True, step) == "groq"
        assert provider_for_tier(False, step) == "groq"

    @pytest.mark.parametrize("step", FOLLOWS_TIER)
    def test_judgement_steps_follow_the_tier(self, auto_settings, step):
        assert provider_for_tier(True, step) == "openai"
        assert provider_for_tier(False, step) == "groq"

    def test_no_step_runs_on_claude_by_default(self, auto_settings):
        # Claude is opt-in (the reel editor's Opus flag, or a pin), never the policy.
        for free, pro in STEP_MODELS.values():
            assert "anthropic" not in (free.provider, pro.provider)

    def test_pro_steps_use_the_configured_openai_model(self, auto_settings):
        assert model_for_step(True, "director").model == "gpt-4.1-mini"
        auto_settings.OPENAI_MODEL = "my-deployment"
        assert model_for_step(True, "director").model == "my-deployment"

    def test_free_director_uses_the_larger_groq_model(self, auto_settings):
        assert model_for_step(False, "director").model == "openai/gpt-oss-120b"

    def test_unlisted_step_follows_the_tier(self, auto_settings):
        # A new step must never be silently downgraded.
        assert provider_for_tier(True, "some_future_step") == "openai"
        assert provider_for_tier(False, "some_future_step") == "groq"

    def test_pinned_provider_outranks_the_policy(self, auto_settings):
        # A pinned run must be genuinely single-provider, or an A/B comparison
        # is measuring two providers at once.
        auto_settings.AI_PROVIDER = "anthropic"
        for step in ALWAYS_FREE + FOLLOWS_TIER:
            assert provider_for_tier(True, step) == "anthropic"
            assert provider_for_tier(False, step) == "anthropic"
        auto_settings.AI_PROVIDER = "groq"
        for step in ALWAYS_FREE + FOLLOWS_TIER:
            assert provider_for_tier(True, step) == "groq"
        auto_settings.AI_PROVIDER = "openai"
        for step in ALWAYS_FREE + FOLLOWS_TIER:
            assert provider_for_tier(True, step) == "openai"
            assert provider_for_tier(False, step) == "openai"

    def test_pro_step_pin_names_an_exact_model(self, auto_settings):
        auto_settings.LLM_PRO_STEP_MODELS = {"director": "openai:gpt-6-astra-1:medium"}
        choice = model_for_step(True, "director")
        assert (choice.provider, choice.model, choice.effort) == ("openai", "gpt-6-astra-1", "medium")
        # Free runs and unpinned steps keep the policy.
        assert model_for_step(False, "director").provider == "groq"
        assert model_for_step(True, "titles").model == "gpt-4.1-mini"

    def test_pinned_provider_outranks_a_pro_step_pin(self, auto_settings):
        auto_settings.LLM_PRO_STEP_MODELS = {"director": "openai:gpt-6-astra-1"}
        auto_settings.AI_PROVIDER = "groq"
        assert model_for_step(True, "director").provider == "groq"

    def test_malformed_pro_step_pin_is_ignored(self, auto_settings):
        auto_settings.LLM_PRO_STEP_MODELS = {"director": "gpt-6-astra-1"}
        assert model_for_step(True, "director").model == "gpt-4.1-mini"

    def test_pinned_claude_step_uses_the_configured_effort(self, auto_settings):
        auto_settings.AI_PROVIDER = "anthropic"
        choice = model_for_step(True, "titles")
        assert (choice.model, choice.effort) == ("claude-opus-5", "high")

    def test_client_factory_builds_the_steps_model(self, auto_settings):
        client = get_text_client(is_pro=True, step="titles")
        assert isinstance(client, OpenAI)
        assert client.model == "gpt-4.1-mini"
        assert isinstance(get_text_client(is_pro=True, step="classification"), Groq)

    def test_exact_choice_still_reaches_claude(self, auto_settings):
        from clients.ai import REEL_DIRECTOR_OPUS

        client = get_text_client(choice=REEL_DIRECTOR_OPUS, step="reel_director")
        assert isinstance(client, Anthropic)
        assert (client.model, client.effort) == ("claude-opus-5-5", "high")

    def test_missing_key_falls_back_to_the_free_provider(self, auto_settings):
        auto_settings.OPENAI_API_KEY = ""
        client = get_text_client(is_pro=True, step="director")
        assert isinstance(client, Groq)
        # The step keeps its own model on the provider it lands on.
        assert client.model == "openai/gpt-oss-120b"

    def test_missing_groq_key_falls_back_to_the_pro_provider(self, auto_settings):
        auto_settings.GROQ_API_KEY = ""
        assert isinstance(get_text_client(is_pro=False, step="titles"), OpenAI)


class TestServiceWiring:
    def test_pro_run_splits_across_both_providers(self, auto_settings):
        service = ContentIntelligenceService(is_pro=True)
        assert isinstance(service._researcher._text_client, OpenAI)
        assert isinstance(service._highlighter._text_client, OpenAI)
        assert isinstance(service._metadata_gen._text_client, OpenAI)
        assert isinstance(service._classifier._text_client, Groq)

    def test_free_run_is_entirely_on_groq(self, auto_settings):
        service = ContentIntelligenceService(is_pro=False)
        for client in (
            service._researcher._text_client,
            service._classifier._text_client,
            service._highlighter._text_client,
            service._metadata_gen._text_client,
        ):
            assert isinstance(client, Groq)


class _Recorder:
    def __init__(self, reply: str = '{"items": []}') -> None:
        self.calls: list[dict] = []
        self._reply = reply

    async def chat(self, messages, **kwargs):
        self.calls.append({"prompt": messages[-1]["content"], **kwargs})
        return self._reply


class TestMetadataBatch:
    def test_title_schema_carries_no_emoji_cues(self):
        assert "emoji_cues" not in TITLE_JSON_SCHEMA["properties"]
        assert set(TITLE_JSON_SCHEMA["required"]) == {"index", "title", "description", "hashtags"}

    @pytest.mark.asyncio
    async def test_all_clips_share_one_call(self):
        client = _Recorder(
            '{"items": [{"index": 0, "title": "A", "description": "d", "hashtags": ["#a"]},'
            ' {"index": 1, "title": "B", "description": "d", "hashtags": ["#b"]}]}'
        )
        clips = await MetadataGenerator(client).generate_batch([
            {"transcript_excerpt": "first", "content_category": "vlog"},
            {"transcript_excerpt": "second", "content_category": "vlog"},
        ])
        assert len(client.calls) == 1
        assert [c["title"] for c in clips] == ["A", "B"]
        assert client.calls[0]["json_schema"] is METADATA_JSON_SCHEMA
        assert "Allowed emoji ids" not in client.calls[0]["prompt"]

    @pytest.mark.asyncio
    async def test_clips_the_director_titled_are_not_sent(self):
        client = _Recorder()
        clips = await MetadataGenerator(client).generate_batch([
            {"transcript_excerpt": "x", "title": "Director title", "content_category": "vlog"},
        ])
        assert client.calls == []
        assert clips[0]["title"] == "Director title"
        assert clips[0]["hashtags"]

    @pytest.mark.asyncio
    async def test_failure_falls_back_without_raising(self):
        class _Broken:
            async def chat(self, messages, **kwargs):
                raise RuntimeError("provider down")

        clips = await MetadataGenerator(_Broken()).generate_batch(
            [{"transcript_excerpt": "I almost lost everything.", "content_category": "vlog"}]
        )
        assert clips[0]["title"]
        assert clips[0]["hashtags"]
        assert clips[0]["ai_emoji_cues"] == []

    @pytest.mark.asyncio
    async def test_an_index_the_model_skipped_gets_a_default(self):
        client = _Recorder('{"items": [{"index": 1, "title": "B", "description": "d", "hashtags": ["#b"]}]}')
        clips = await MetadataGenerator(client).generate_batch([
            {"transcript_excerpt": "Money talks.", "content_category": "vlog"},
            {"transcript_excerpt": "second", "content_category": "vlog"},
        ])
        assert clips[0]["title"] and clips[0]["title"] != "B"
        assert clips[1]["title"] == "B"


class TestClipDensity:
    @pytest.mark.parametrize(
        "duration,expected",
        [(3600.0, 20), (1800.0, 10), (300.0, MIN_CLIPS), (0.0, MIN_CLIPS)],
    )
    def test_density_is_one_clip_per_three_minutes(self, duration, expected):
        assert HighlightDetector._max_clips(duration, MAX_CLIPS_PER_HOUR) == expected

    def test_density_dropped_from_the_previous_sixty_per_hour(self):
        # Each clip costs a metadata call, so density is a cost lever as well as
        # a product one.
        assert MAX_CLIPS_PER_HOUR == 20.0
        assert HighlightDetector._max_clips(3600.0, MAX_CLIPS_PER_HOUR) < 60

    def test_explicit_setting_still_overrides(self):
        assert HighlightDetector._max_clips(3600.0, MAX_CLIPS_PER_HOUR, explicit=8) == 8


class TestOpenAIRouting:
    """LLM_ROUTING=openai runs every step of every plan on OpenAI; Groq stays the fallback."""

    @pytest.mark.parametrize("step", ALWAYS_FREE + FOLLOWS_TIER + ("social_copy", "reel_director", None))
    def test_every_step_runs_on_openai_for_both_plans(self, auto_settings, step):
        auto_settings.LLM_ROUTING = "openai"
        assert provider_for_tier(False, step) == "openai"
        assert provider_for_tier(True, step) == "openai"
        assert model_for_step(False, step).model == "gpt-4.1-mini"

    def test_missing_openai_key_still_falls_back_to_groq(self, auto_settings):
        auto_settings.LLM_ROUTING = "openai"
        auto_settings.OPENAI_API_KEY = ""
        assert isinstance(get_text_client(is_pro=False, step="director"), Groq)

    def test_tiered_routing_restores_the_groq_policy(self, auto_settings):
        auto_settings.LLM_ROUTING = "tiered"
        assert provider_for_tier(False, "director") == "groq"
        assert provider_for_tier(True, "director") == "openai"

    def test_opus_flag_yields_to_openai_routing(self, auto_settings):
        from edit_engine.director import director_client

        auto_settings.LLM_ROUTING = "openai"
        assert isinstance(director_client(is_pro=True, opus=True), OpenAI)
