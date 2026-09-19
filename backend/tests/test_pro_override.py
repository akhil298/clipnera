from __future__ import annotations

import pytest

from subscription.model import PlanSlug
from subscription.service import SubscriptionService, pro_override_emails


class _User:
    def __init__(self, email: str | None) -> None:
        self.email = email


class _Sub:
    def __init__(self, plan_id: str = "plan-free") -> None:
        self.id = "sub-1"
        self.plan_id = plan_id


class _Plan:
    def __init__(self, slug: str) -> None:
        self.slug = slug


class _SubRepo:
    def __init__(self, subscription=None) -> None:
        self._subscription = subscription

    async def get_active_by_user(self, user_id: str):
        return self._subscription


class _PlanRepo:
    def __init__(self, plan=None) -> None:
        self._plan = plan

    async def get_by_id(self, plan_id: str):
        return self._plan


def _service(subscription=None, plan=None) -> SubscriptionService:
    return SubscriptionService(_PlanRepo(plan), _SubRepo(subscription), None, None)


def _patch_override(monkeypatch, emails: str, user: _User | None = _User("someone@example.com"),
                    raises: bool = False):
    """Point the override list and the user lookup at test doubles."""
    import subscription.service as svc

    class _Settings:
        PRO_OVERRIDE_EMAILS = emails

    monkeypatch.setattr(svc, "get_settings", lambda: _Settings())

    class _Session:
        async def __aenter__(self):
            if raises:
                raise RuntimeError("database unavailable")
            return self

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(svc, "AsyncSessionLocal", _Session)

    class _UserRepo:
        def __init__(self, session):
            pass

        async def get_by_id(self, user_id: str):
            return user

    import user.repository as user_repo
    monkeypatch.setattr(user_repo, "UserRepository", _UserRepo)


class TestParsingTheList:
    def test_empty_setting_is_an_empty_set(self, monkeypatch):
        _patch_override(monkeypatch, "")
        assert pro_override_emails() == frozenset()

    def test_entries_are_lowercased_and_stripped(self, monkeypatch):
        _patch_override(monkeypatch, "  Akhil@Example.COM , other@x.io ")
        assert pro_override_emails() == {"akhil@example.com", "other@x.io"}

    def test_blank_entries_are_dropped(self, monkeypatch):
        # A trailing comma must not put "" in the set, or a user with no email
        # on record would match it.
        _patch_override(monkeypatch, "a@b.com,,")
        assert pro_override_emails() == {"a@b.com"}


class TestOverrideBehaviour:
    @pytest.mark.asyncio
    async def test_listed_email_is_pro_without_a_subscription(self, monkeypatch):
        _patch_override(monkeypatch, "akhil@example.com", _User("akhil@example.com"))
        service = _service(subscription=None)
        assert await service.get_user_plan_slug("u1") == PlanSlug.PRO.value
        assert await service.is_pro_user("u1") is True

    @pytest.mark.asyncio
    async def test_match_ignores_case(self, monkeypatch):
        _patch_override(monkeypatch, "akhil@example.com", _User("AKHIL@Example.com"))
        assert await _service().get_user_plan_slug("u1") == PlanSlug.PRO.value

    @pytest.mark.asyncio
    async def test_unlisted_email_still_resolves_to_free(self, monkeypatch):
        _patch_override(monkeypatch, "akhil@example.com", _User("stranger@example.com"))
        assert await _service().get_user_plan_slug("u1") == PlanSlug.FREE.value

    @pytest.mark.asyncio
    async def test_empty_list_disables_the_override_entirely(self, monkeypatch):
        _patch_override(monkeypatch, "", _User("akhil@example.com"))
        assert await _service().get_user_plan_slug("u1") == PlanSlug.FREE.value

    @pytest.mark.asyncio
    async def test_user_without_an_email_never_matches(self, monkeypatch):
        _patch_override(monkeypatch, "akhil@example.com", _User(None))
        assert await _service().get_user_plan_slug("u1") == PlanSlug.FREE.value

    @pytest.mark.asyncio
    async def test_missing_user_row_never_matches(self, monkeypatch):
        _patch_override(monkeypatch, "akhil@example.com", None)
        assert await _service().get_user_plan_slug("u1") == PlanSlug.FREE.value

    @pytest.mark.asyncio
    async def test_lookup_failure_does_not_upgrade(self, monkeypatch):
        # Erring toward free matters more here than anywhere: a database blip
        # must not hand paid inference to every user at once.
        _patch_override(monkeypatch, "akhil@example.com", _User("akhil@example.com"), raises=True)
        assert await _service().get_user_plan_slug("u1") == PlanSlug.FREE.value

    @pytest.mark.asyncio
    async def test_a_real_paid_subscription_still_wins_without_the_override(self, monkeypatch):
        _patch_override(monkeypatch, "", _User("paying@example.com"))
        service = _service(subscription=_Sub("plan-pro"), plan=_Plan(PlanSlug.PRO.value))
        assert await service.get_user_plan_slug("u1") == PlanSlug.PRO.value
