from __future__ import annotations

import pytest

from clients.ai import STEP_POLICY, get_text_client, provider_for_tier
from clients.ai.anthropic import Anthropic
from clients.ai.groq import Groq
from content_intelligence.highlighter import MAX_CLIPS_PER_HOUR, MIN_CLIPS, HighlightDetector
from content_intelligence.metadata_gen import (
    CUES_JSON_SCHEMA,
    TITLE_JSON_SCHEMA,
    MetadataGenerator,
)
from content_intelligence.service import ContentIntelligenceService

# Steps pinned to the free provider whatever the user pays.
ALWAYS_FREE = ("classification", "emoji_cues")
# Steps that follow the user's tier.
FOLLOWS_TIER = ("topic_research", "highlight_detection", "titles")


class TestStepPolicy:
    @pytest.mark.parametrize("step", ALWAYS_FREE)
    def test_cheap_steps_stay_on_groq_even_for_pro(self, step):
        assert STEP_POLICY[step] == "groq"
        assert provider_for_tier(True, step) == "groq"
        assert provider_for_tier(False, step) == "groq"

    @pytest.mark.parametrize("step", FOLLOWS_TIER)
    def test_judgement_steps_follow_the_tier(self, step):
        assert STEP_POLICY[step] == "tier"
        assert provider_for_tier(True, step) == "anthropic"
        assert provider_for_tier(False, step) == "groq"

    def test_unlisted_step_follows_the_tier(self):
        # A new step must never be silently downgraded; it costs what the tier
        # costs until someone classifies it.
        assert provider_for_tier(True, "some_future_step") == "anthropic"

    def test_no_step_still_follows_the_tier(self):
        assert provider_for_tier(True) == "anthropic"
        assert provider_for_tier(False) == "groq"

    def test_pinned_provider_outranks_the_policy(self, monkeypatch):
        # A pinned run must be genuinely single-provider, or an A/B comparison
        # is measuring two providers at once.
        import clients.ai as ai

        class _Pinned:
            AI_PROVIDER = "anthropic"
            GROQ_API_KEY = "x"
            ANTHROPIC_API_KEY = "x"

        monkeypatch.setattr(ai, "get_settings", lambda: _Pinned())
        for step in ALWAYS_FREE + FOLLOWS_TIER:
            assert ai.provider_for_tier(True, step) == "anthropic"
            assert ai.provider_for_tier(False, step) == "anthropic"

    def test_client_factory_honours_the_step(self):
        assert isinstance(get_text_client(is_pro=True, step="emoji_cues"), Groq)
        assert isinstance(get_text_client(is_pro=True, step="titles"), Anthropic)


class TestServiceWiring:
    def test_pro_run_splits_across_both_providers(self):
        service = ContentIntelligenceService(is_pro=True)
        assert isinstance(service._researcher._text_client, Anthropic)
        assert isinstance(service._highlighter._text_client, Anthropic)
        assert isinstance(service._metadata_gen._text_client, Anthropic)
        # The two that must stay cheap.
        assert isinstance(service._classifier._text_client, Groq)
        assert isinstance(service._metadata_gen._cue_client, Groq)

    def test_free_run_is_entirely_on_groq(self):
        service = ContentIntelligenceService(is_pro=False)
        for client in (
            service._researcher._text_client,
            service._classifier._text_client,
            service._highlighter._text_client,
            service._metadata_gen._text_client,
            service._metadata_gen._cue_client,
        ):
            assert isinstance(client, Groq)


class TestMetadataSplit:
    def test_cue_client_defaults_to_the_text_client(self):
        # A caller written before the split must keep working.
        sentinel = object()
        assert MetadataGenerator(sentinel)._cue_client is sentinel

    def test_title_schema_carries_no_emoji_cues(self):
        # The 306-token catalogue is only needed to produce cues; keeping cues
        # out of the title call is what removes it from the paid request.
        assert "emoji_cues" not in TITLE_JSON_SCHEMA["properties"]
        assert set(TITLE_JSON_SCHEMA["required"]) == {"title", "description", "hashtags"}

    def test_cue_schema_carries_only_cues(self):
        assert set(CUES_JSON_SCHEMA["properties"]) == {"emoji_cues"}

    @pytest.mark.asyncio
    async def test_title_prompt_excludes_the_emoji_catalogue(self):
        captured: dict = {}

        class _Client:
            async def chat(self, messages, **kwargs):
                captured["prompt"] = messages[-1]["content"]
                captured["schema"] = kwargs.get("json_schema")
                return '{"title":"T","description":"D","hashtags":["#a"]}'

        generator = MetadataGenerator(_Client(), cue_client=_Client())
        await generator._generate_title({"transcript_excerpt": "money and growth"}, "vlog")

        assert "Allowed emoji ids" not in captured["prompt"]
        assert captured["schema"] is TITLE_JSON_SCHEMA

    @pytest.mark.asyncio
    async def test_cues_go_to_the_cue_client_not_the_title_client(self):
        calls: list[str] = []

        class _Client:
            def __init__(self, name):
                self._name = name

            async def chat(self, messages, **kwargs):
                calls.append(self._name)
                if self._name == "title":
                    return '{"title":"T","description":"D","hashtags":["#a"]}'
                return '{"emoji_cues":[]}'

        generator = MetadataGenerator(_Client("title"), cue_client=_Client("cue"))
        await generator._generate_for_clip({"transcript_excerpt": "money", "content_category": "vlog"})

        assert calls == ["title", "cue"]

    @pytest.mark.asyncio
    async def test_cue_failure_does_not_cost_the_clip_its_title(self):
        class _Title:
            async def chat(self, messages, **kwargs):
                return '{"title":"Real Title","description":"D","hashtags":["#a"]}'

        class _Broken:
            async def chat(self, messages, **kwargs):
                raise RuntimeError("cue provider down")

        generator = MetadataGenerator(_Title(), cue_client=_Broken())
        clip = await generator._generate_for_clip(
            {"transcript_excerpt": "money", "content_category": "vlog"}
        )

        assert clip["title"] == "Real Title"
        assert clip["ai_emoji_cues"] == []

    @pytest.mark.asyncio
    async def test_title_failure_falls_back_without_raising(self):
        class _Broken:
            async def chat(self, messages, **kwargs):
                raise RuntimeError("title provider down")

        class _Cues:
            async def chat(self, messages, **kwargs):
                return '{"emoji_cues":[]}'

        generator = MetadataGenerator(_Broken(), cue_client=_Cues())
        clip = await generator._generate_for_clip(
            {"transcript_excerpt": "I almost lost everything.", "content_category": "vlog"}
        )

        assert clip["title"]
        assert clip["hashtags"]


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
