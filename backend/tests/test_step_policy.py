from __future__ import annotations

import pytest

from clients.ai import STEP_MODELS, get_text_client, model_for_step, provider_for_tier
from clients.ai.anthropic import Anthropic
from clients.ai.groq import Groq
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
    ANTHROPIC_MODEL = "claude-opus-5"
    ANTHROPIC_EFFORT = "medium"
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
        assert provider_for_tier(True, step) == "anthropic"
        assert provider_for_tier(False, step) == "groq"

    def test_pro_uses_opus_only_where_clips_are_chosen(self, auto_settings):
        # The costly model is reserved for picking and editing the moments.
        for step, (_, pro) in STEP_MODELS.items():
            if pro.model == "claude-opus-5":
                assert step in ("highlight_detection", "director")

    def test_no_pro_step_runs_at_high_effort(self, auto_settings):
        # Hidden thinking at high effort on every call was most of the old bill.
        for _, pro in STEP_MODELS.values():
            assert pro.effort in (None, "low", "medium")

    def test_free_director_uses_the_larger_groq_model(self, auto_settings):
        assert model_for_step(False, "director").model == "openai/gpt-oss-120b"

    def test_unlisted_step_follows_the_tier(self, auto_settings):
        # A new step must never be silently downgraded.
        assert provider_for_tier(True, "some_future_step") == "anthropic"
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

    def test_client_factory_builds_the_steps_model(self, auto_settings):
        client = get_text_client(is_pro=True, step="titles")
        assert isinstance(client, Anthropic)
        assert (client.model, client.effort) == ("claude-sonnet-5", "low")
        director = get_text_client(is_pro=True, step="highlight_detection")
        assert (director.model, director.effort) == ("claude-opus-5", "medium")
        assert isinstance(get_text_client(is_pro=True, step="classification"), Groq)

    def test_missing_key_falls_back_to_the_other_provider(self, auto_settings):
        auto_settings.ANTHROPIC_API_KEY = ""
        assert isinstance(get_text_client(is_pro=True, step="titles"), Groq)


class TestServiceWiring:
    def test_pro_run_splits_across_both_providers(self, auto_settings):
        service = ContentIntelligenceService(is_pro=True)
        assert isinstance(service._researcher._text_client, Anthropic)
        assert isinstance(service._highlighter._text_client, Anthropic)
        assert isinstance(service._metadata_gen._text_client, Anthropic)
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
