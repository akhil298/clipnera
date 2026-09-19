from __future__ import annotations

import pytest

from clients.ai import FREE_TEXT_PROVIDER, PRO_TEXT_PROVIDER, get_text_client, provider_for_tier
from clients.ai.anthropic import Anthropic
from clients.ai.groq import Groq
from content_intelligence.service import ContentIntelligenceService
from pipeline.model import PipelineStepType
from pipeline.service import PipelineOrchestrator
from subscription.model import PlanSlug
from subscription.service import PAID_PLAN_SLUGS, SubscriptionService


class _Sub:
    def __init__(self, plan_id: str) -> None:
        self.id = "sub-1"
        self.plan_id = plan_id


class _Plan:
    def __init__(self, slug) -> None:
        self.slug = slug


class _SubRepo:
    def __init__(self, subscription=None, raises=False) -> None:
        self._subscription = subscription
        self._raises = raises

    async def get_active_by_user(self, user_id: str):
        if self._raises:
            raise RuntimeError("database unavailable")
        return self._subscription


class _PlanRepo:
    def __init__(self, plan=None) -> None:
        self._plan = plan

    async def get_by_id(self, plan_id: str):
        return self._plan


def _service(sub_repo, plan_repo) -> SubscriptionService:
    return SubscriptionService(plan_repo, sub_repo, None, None)


class TestIsProUser:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("slug", sorted(PAID_PLAN_SLUGS))
    async def test_paid_plans_are_pro(self, slug):
        service = _service(_SubRepo(_Sub("plan-1")), _PlanRepo(_Plan(slug)))
        assert await service.is_pro_user("u1") is True

    @pytest.mark.asyncio
    async def test_free_plan_is_not_pro(self):
        service = _service(_SubRepo(_Sub("plan-1")), _PlanRepo(_Plan(PlanSlug.FREE.value)))
        assert await service.is_pro_user("u1") is False

    @pytest.mark.asyncio
    async def test_enum_slug_is_accepted_not_just_the_string(self):
        # The ORM hands back the enum; comparing it to raw strings without
        # unwrapping would make every paid user look free.
        service = _service(_SubRepo(_Sub("plan-1")), _PlanRepo(_Plan(PlanSlug.PRO)))
        assert await service.is_pro_user("u1") is True

    @pytest.mark.asyncio
    async def test_no_active_subscription_is_not_pro(self):
        service = _service(_SubRepo(None), _PlanRepo(None))
        assert await service.is_pro_user("u1") is False

    @pytest.mark.asyncio
    async def test_missing_plan_row_is_not_pro(self):
        service = _service(_SubRepo(_Sub("ghost")), _PlanRepo(None))
        assert await service.is_pro_user("u1") is False

    @pytest.mark.asyncio
    async def test_lookup_failure_degrades_to_free(self):
        # Erring toward free means a database blip costs quality, not money
        # billed to someone who is not paying for it.
        service = _service(_SubRepo(raises=True), _PlanRepo(None))
        assert await service.is_pro_user("u1") is False


class TestProviderForTier:
    def test_pro_and_free_map_to_different_providers(self):
        assert provider_for_tier(True) == PRO_TEXT_PROVIDER
        assert provider_for_tier(False) == FREE_TEXT_PROVIDER
        assert PRO_TEXT_PROVIDER != FREE_TEXT_PROVIDER

    def test_client_follows_the_flag(self):
        assert isinstance(get_text_client(is_pro=True), Anthropic)
        assert isinstance(get_text_client(is_pro=False), Groq)

    def test_explicit_provider_overrides_the_flag(self):
        # An A/B run pins the provider regardless of tier.
        assert isinstance(get_text_client(provider="groq", is_pro=True), Groq)

    def test_env_override_pins_every_tier(self, monkeypatch):
        import clients.ai as ai

        class _Pinned:
            AI_PROVIDER = "groq"
            GROQ_API_KEY = "x"
            ANTHROPIC_API_KEY = "x"

        monkeypatch.setattr(ai, "get_settings", lambda: _Pinned())
        assert ai.provider_for_tier(True) == "groq"
        assert ai.provider_for_tier(False) == "groq"


class TestTierReachesTheClient:
    @pytest.mark.parametrize("is_pro,expected", [(True, Anthropic), (False, Groq)])
    def test_content_service_uses_the_tier_provider(self, is_pro, expected):
        assert isinstance(ContentIntelligenceService(is_pro=is_pro)._text_client, expected)

    @pytest.mark.parametrize("is_pro", [True, False])
    def test_orchestrator_carries_the_flag(self, is_pro):
        orchestrator = PipelineOrchestrator(
            "project", "user", "url", [PipelineStepType.HIGHLIGHT_DETECTION], is_pro=is_pro,
        )
        assert orchestrator.is_pro is is_pro

    def test_orchestrator_defaults_to_free(self):
        # A caller that forgets the flag must not silently bill paid inference.
        orchestrator = PipelineOrchestrator(
            "project", "user", "url", [PipelineStepType.HIGHLIGHT_DETECTION],
        )
        assert orchestrator.is_pro is False

    def test_pro_window_is_far_larger(self):
        pro = ContentIntelligenceService(is_pro=True)._text_client
        free = ContentIntelligenceService(is_pro=False)._text_client
        assert pro.input_token_budget(2600) > free.input_token_budget(2600) * 10
