"""Free vs Pro rules and their enforcement on the API, without a database."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from auth.dependencies import get_current_user
from core.exceptions import CustomException
from subscription.dependencies import get_subscription_service
from subscription.entitlements import (
    ENTITLEMENTS,
    PLAN_PRICES,
    PURCHASABLE_PLAN,
    entitlements_for,
)
from subscription.model import BillingPeriod, PlanSlug
from subscription.service import SubscriptionService, cycle_start, pro_required


# Config


def test_new_gates_are_pro_only():
    free, pro = entitlements_for("free"), entitlements_for("pro")
    for feature in ("all_hook_transitions", "brand_kit_edit", "depth_captions", "batch_processing", "team_members"):
        assert not free.allows(feature)
        assert pro.allows(feature)


def test_free_limits_and_pro_unlimited():
    assert entitlements_for("free").daily_limits == {
        "exports": 10, "audio_enhancements": 3, "reel_renders": 2, "ai_shots": 0, "auto_edits": 1,
    }
    # Pro: unlimited exports and enhancements, fair-use caps on reels, footage edits and AI shots.
    assert entitlements_for("pro").daily_limits == {
        "exports": None, "audio_enhancements": None, "reel_renders": 20, "ai_shots": 10, "auto_edits": 15,
    }
    assert entitlements_for("free").credit_minutes == 20
    assert entitlements_for("pro").credit_minutes == 600


def test_pro_plus_keeps_its_limits_but_is_not_sold():
    assert entitlements_for("pro_plus").credit_minutes == 1200
    assert PURCHASABLE_PLAN == PlanSlug.PRO.value


def test_yearly_is_about_two_months_cheaper():
    monthly, yearly = PLAN_PRICES[BillingPeriod.MONTHLY], PLAN_PRICES[BillingPeriod.YEARLY]
    assert (monthly.amount_inr, monthly.days) == (699, 30)
    assert (yearly.amount_inr, yearly.days) == (6990, 365)
    assert yearly.amount_inr == 10 * monthly.amount_inr


@pytest.mark.parametrize(
    ("mode", "free_ok"), [(None, True), ("auto", True), ("off", True), ("preset", False), ("custom", False)]
)
def test_free_hook_transitions_are_auto_only(mode, free_ok):
    assert entitlements_for("free").allows_hook_transition(mode) is free_ok
    assert entitlements_for("pro").allows_hook_transition(mode) is True


def test_every_plan_exposes_the_same_feature_names():
    names = {slug: set(ent.features()) for slug, ent in ENTITLEMENTS.items()}
    assert len({frozenset(n) for n in names.values()}) == 1


def test_pro_required_error_names_the_feature():
    body = pro_required("depth_captions").to_dict()
    assert body == {"error": "PRO_REQUIRED", "feature": "depth_captions", "message": "Upgrade to Pro to use this feature."}


def test_cycle_start_counts_whole_cycles_from_the_anchor():
    anchor = datetime(2026, 1, 1, 12)
    assert cycle_start(anchor, anchor) == anchor
    assert cycle_start(anchor, anchor + timedelta(days=29, hours=23)) == anchor
    assert cycle_start(anchor, anchor + timedelta(days=30)) == anchor + timedelta(days=30)
    assert cycle_start(anchor, anchor + timedelta(days=95)) == anchor + timedelta(days=90)


# Direct API calls


class _PlanService(SubscriptionService):
    """The real service with the plan lookup and quota pinned."""

    def __init__(self, plan: str) -> None:
        super().__init__(None, None, None, None)
        self.plan = plan

    async def get_effective_plan(self, user_id: str) -> str:
        return self.plan

    async def consume_daily_quota(self, user_id, key, amount=1):
        if self.plan == "free":
            raise CustomException(message="limit", code="LIMIT_REACHED", status_code=429, extra={"feature": key})
        return 1


GATED_ROUTES = [
    ("post", "/api/v1/depth-captions/render", "depth_captions"),
    ("post", "/api/v1/brand-kits", "brand_kit_edit"),
    ("post", "/api/v1/transcription/batch", "batch_processing"),
    ("post", "/api/v1/audio/extraction/batch", "batch_processing"),
    ("post", "/api/v1/workspaces/ws-1/members", "team_members"),
    ("post", "/api/v1/workspaces/ws-1/members/create", "team_members"),
    ("post", "/api/v1/hook-transitions/clips/clip-1/resolve", "all_hook_transitions"),
]


@pytest.fixture
def client_for():
    def make(plan: str) -> TestClient:
        main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
        main.app.dependency_overrides[get_subscription_service] = lambda: _PlanService(plan)
        return TestClient(main.app, raise_server_exceptions=False)

    yield make
    main.app.dependency_overrides.clear()


def _body(path: str) -> dict:
    # Enough to pass validation where the body is parsed before the gate.
    return {"mode": "preset", "preset_id": "viral_rewind"} if "hook-transitions" in path else {}


@pytest.mark.parametrize(("method", "path", "feature"), GATED_ROUTES)
def test_free_user_calling_a_pro_route_directly_gets_pro_required(client_for, method, path, feature):
    response = getattr(client_for("free"), method)(path, json=_body(path))
    assert response.status_code == 403
    assert response.json()["error"] == "PRO_REQUIRED"
    assert response.json()["feature"] == feature


@pytest.mark.parametrize(("method", "path", "feature"), GATED_ROUTES)
def test_pro_user_passes_the_gate(client_for, method, path, feature):
    response = getattr(client_for("pro"), method)(path, json=_body(path))
    # Whatever happens next (validation, missing records), it is not the plan gate.
    assert response.json().get("error") != "PRO_REQUIRED"


def test_free_audio_enhancement_limit_returns_limit_reached(client_for):
    response = client_for("free").post("/api/v1/audio/process", json={})
    assert response.status_code == 429
    assert response.json()["error"] == "LIMIT_REACHED"
    assert response.json()["feature"] == "audio_enhancements"


def test_plans_endpoint_lists_prices_from_config(client_for, monkeypatch):
    class _Plan:
        def __init__(self, slug, name):
            self.slug, self.name = slug, name

    async def _list_plans(self):
        return [_Plan("free", "Free"), _Plan("pro", "Pro")]

    monkeypatch.setattr(_PlanService, "list_plans", _list_plans)
    data = client_for("free").get("/api/v1/subscription/plans").json()

    free, pro = data["plans"]
    assert free["prices"] == []
    assert free["capabilities"]["features"]["brand_kit_edit"] is False
    assert {p["plan_type"]: p["amount"] for p in pro["prices"]} == {"monthly": 699, "yearly": 6990}
    assert pro["capabilities"]["credit_minutes"] == 600


@pytest.mark.parametrize(("plan", "refused"), [("free", True), ("pro", False)])
def test_export_with_a_preset_hook_transition_needs_pro(plan, refused):
    from clip_generation.schema import SocialExportRequest
    from pipeline.service import _check_export_entitlements

    request = SocialExportRequest(hook_transition={"mode": "preset", "preset_id": "viral_rewind"})
    if refused:
        with pytest.raises(CustomException) as exc:
            _check_export_entitlements(entitlements_for(plan), request)
        assert exc.value.code == "PRO_REQUIRED"
    else:
        _check_export_entitlements(entitlements_for(plan), request)


def test_export_with_auto_hook_transition_is_free():
    from clip_generation.schema import SocialExportRequest
    from pipeline.service import _check_export_entitlements

    _check_export_entitlements(entitlements_for("free"), SocialExportRequest(hook_transition={"mode": "auto"}))
