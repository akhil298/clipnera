from __future__ import annotations

import pytest

from usage.context import LlmBudgetExceeded, RunBudget, check_budget, current_scope, llm_scope
from usage.pricing import audio_cost, token_cost
from usage import recorder


class TestPricing:
    def test_opus_token_cost(self):
        # 1M in at $5, 1M out at $25
        assert token_cost("anthropic", "claude-opus-5", 1_000_000, 1_000_000) == pytest.approx(30.0)

    def test_cache_multipliers(self):
        cost = token_cost("anthropic", "claude-sonnet-5", 0, 0, cache_read_tokens=1_000_000, cache_write_tokens=1_000_000)
        assert cost == pytest.approx(2.0 * 0.1 + 2.0 * 1.25)

    def test_unknown_model_costs_zero(self):
        assert token_cost("groq", "no-such-model", 1000, 1000) == 0.0

    def test_audio_is_per_hour(self):
        assert audio_cost("groq", "whisper-large-v3-turbo", 3600) == pytest.approx(0.04)


class TestBudget:
    def test_states(self):
        budget = RunBudget(cap_usd=1.0)
        assert not budget.tight and not budget.exhausted
        budget.charge(0.85)
        assert budget.tight and not budget.exhausted
        budget.charge(0.2)
        assert budget.exhausted

    def test_zero_cap_is_unlimited(self):
        budget = RunBudget(cap_usd=0.0)
        budget.charge(1000)
        assert not budget.exhausted

    def test_check_raises_only_inside_an_exhausted_scope(self):
        assert check_budget() is None
        with llm_scope(project_id="p", step="map", budget=RunBudget(cap_usd=0.01, spent_usd=0.02)):
            with pytest.raises(LlmBudgetExceeded):
                check_budget()
        assert current_scope() is None

    def test_scopes_nest_and_restore(self):
        with llm_scope(project_id="p", step="a"):
            with llm_scope(step="b"):
                assert current_scope().project_id == "p" and current_scope().step == "b"
            assert current_scope().step == "a"


class TestRecorder:
    @pytest.mark.asyncio
    async def test_unscoped_calls_are_not_written(self, monkeypatch):
        def boom():
            raise AssertionError("must not open a session outside a scope")

        monkeypatch.setattr(recorder, "AsyncSessionLocal", boom)
        cost = await recorder.record_llm_call("anthropic", "claude-opus-5", input_tokens=1000, output_tokens=1000)
        assert cost == pytest.approx(0.03)

    @pytest.mark.asyncio
    async def test_scoped_calls_charge_the_budget_and_persist(self, monkeypatch):
        added = []

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            def add(self, row):
                added.append(row)

            async def commit(self):
                pass

        monkeypatch.setattr(recorder, "AsyncSessionLocal", _Session)
        budget = RunBudget(cap_usd=1.0)
        with llm_scope(project_id="p1", user_id="u1", step="director", budget=budget):
            await recorder.record_llm_call("anthropic", "claude-opus-5", input_tokens=1000, output_tokens=1000,
                                           effort="medium")
        assert budget.spent_usd == pytest.approx(0.03)
        assert added[0].project_id == "p1" and added[0].step == "director" and added[0].effort == "medium"

    @pytest.mark.asyncio
    async def test_a_failed_write_never_raises(self, monkeypatch):
        def broken():
            raise RuntimeError("db down")

        monkeypatch.setattr(recorder, "AsyncSessionLocal", broken)
        with llm_scope(project_id="p1", step="map"):
            await recorder.record_llm_call("groq", "openai/gpt-oss-20b", input_tokens=10, output_tokens=10)


class TestCostPerMinute:
    def test_pro_and_free_are_measured_separately(self):
        from usage.service import cost_per_minute

        rows = [(0.30, 1200, True), (0.10, 600, True), (0.02, 1200, False), (0.5, None, True)]
        by_tier = {c.tier: c for c in cost_per_minute(rows)}
        assert by_tier["pro"].projects == 2 and by_tier["pro"].source_minutes == 30.0
        assert by_tier["pro"].cost_per_source_minute_usd == pytest.approx(0.40 / 30, abs=1e-5)
        assert by_tier["free"].cost_per_source_minute_usd == pytest.approx(0.001, abs=1e-5)
