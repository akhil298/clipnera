from __future__ import annotations

import pytest

from clients.ai.groq import DEFAULT_REASONING_EFFORT, Groq, get_profile, input_token_budget
from clip_generation.service import ClipService


def _client(model: str) -> Groq:
    """A Groq wrapper without the network client, for testing its own logic."""
    client = Groq.__new__(Groq)
    client.model = model
    client.profile = get_profile(model)
    return client


class TestEmptyReplyHandling:
    """A reasoning model that spends its whole budget thinking returns "".

    That is what silently emptied highlight detection: every window produced no
    moments, the pipeline fell through to its fallback, and the fallback shipped
    a single clip.
    """

    @pytest.mark.asyncio
    async def test_empty_first_reply_is_retried_with_more_room(self):
        client = _client("openai/gpt-oss-20b")
        calls: list[int] = []

        async def fake_once(messages, json_mode=False, **kwargs):
            calls.append(int(kwargs.get("max_tokens") or 0))
            return "" if len(calls) == 1 else '{"moments": []}'

        client._chat_once = fake_once
        result = await client.chat([{"role": "user", "content": "hi"}], max_tokens=1400)

        assert result == '{"moments": []}'
        assert len(calls) == 2
        assert calls[1] > calls[0]

    @pytest.mark.asyncio
    async def test_persistently_empty_reply_raises_instead_of_returning_blank(self):
        client = _client("openai/gpt-oss-20b")

        async def always_empty(messages, json_mode=False, **kwargs):
            return "   "

        client._chat_once = always_empty
        with pytest.raises(RuntimeError, match="no content"):
            await client.chat([{"role": "user", "content": "hi"}], max_tokens=1400)

    @pytest.mark.asyncio
    async def test_a_good_reply_is_not_retried(self):
        client = _client("openai/gpt-oss-20b")
        calls: list[int] = []

        async def fake_once(messages, json_mode=False, **kwargs):
            calls.append(1)
            return '{"ok": true}'

        client._chat_once = fake_once
        assert await client.chat([{"role": "user", "content": "hi"}]) == '{"ok": true}'
        assert len(calls) == 1


class TestTokenBudget:
    def test_budget_leaves_room_for_the_reply(self):
        budget = input_token_budget(1400, "openai/gpt-oss-20b")
        profile = get_profile("openai/gpt-oss-20b")
        assert 0 < budget < profile.tokens_per_minute

    def test_reasoning_models_are_configured_with_a_low_effort_default(self):
        assert DEFAULT_REASONING_EFFORT == "low"


class TestClipScoreSurface:
    def test_virality_components_reach_the_api_response(self):
        # The UI reads scores.hook_score / scores.engagement_score; they lived
        # only under scoring_factors, so every clip showed the overall score
        # three times over.
        clip = {
            "score": 80.0,
            "scoring_factors": {
                "virality_scores": {
                    "hook_score": 20.0,
                    "engagement_score": 12.5,
                    "value_score": 5.0,
                    "shareability_score": 25.0,
                    "virality_score": 62.5,
                },
            },
        }

        scores = ClipService._clip_scores(clip, [])

        assert scores["hook_score"] == pytest.approx(0.8)
        assert scores["engagement_score"] == pytest.approx(0.5)
        assert scores["shareability_score"] == pytest.approx(1.0)
        assert scores["virality_score"] == pytest.approx(0.625)

    def test_missing_breakdown_does_not_raise(self):
        scores = ClipService._clip_scores({"score": 40.0}, [])
        assert scores["hook_score"] == 0.0
        assert scores["clip_quality"] == pytest.approx(0.4)
