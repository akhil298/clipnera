"""Sign-up consent, email unsubscribe and self-service account deletion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import user.service as user_service
from auth.service import AuthService
from core.exceptions import CustomException
from user.service import UserService
from user.unsubscribe import unsubscribe_token, user_id_from_token


class _UserRepo:
    def __init__(self, user=None) -> None:
        self.user = user
        self.email_notifications: dict[str, bool] = {}
        self.deleted: list[str] = []

    async def get_by_id(self, user_id):
        return self.user if self.user and self.user.id == user_id else None

    async def set_email_notifications(self, user_id, enabled):
        self.email_notifications[user_id] = enabled

    async def delete(self, user_id):
        self.deleted.append(user_id)


class _Social:
    def __init__(self) -> None:
        self.purged: list[str] = []

    async def purge_user(self, user_id):
        self.purged.append(user_id)


def _user(email: str = "Ada@Example.com"):
    return SimpleNamespace(id="user-1", email=email)


# -- unsubscribe links ------------------------------------------------------


def test_unsubscribe_token_round_trips():
    assert user_id_from_token(unsubscribe_token("user-1")) == "user-1"


@pytest.mark.parametrize("token", ["", "user-1", unsubscribe_token("user-1") + "x"])
def test_forged_unsubscribe_token_is_rejected(token):
    assert user_id_from_token(token) is None


@pytest.mark.asyncio
async def test_unsubscribe_turns_off_account_emails():
    repo = _UserRepo(_user())
    await UserService(repo).unsubscribe(unsubscribe_token("user-1"))
    assert repo.email_notifications == {"user-1": False}


@pytest.mark.asyncio
async def test_unsubscribe_with_invalid_token_fails():
    with pytest.raises(CustomException) as exc:
        await UserService(_UserRepo(_user())).unsubscribe("not-a-token")
    assert exc.value.code == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_unsubscribe_after_account_deletion_succeeds_quietly():
    repo = _UserRepo(None)
    await UserService(repo).unsubscribe(unsubscribe_token("user-1"))
    assert repo.email_notifications == {}


# -- account deletion -------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_account_requires_the_account_email(monkeypatch):
    monkeypatch.setattr(user_service, "_delete_user_files", lambda user_id: pytest.fail("files deleted"))
    repo, social = _UserRepo(_user()), _Social()
    with pytest.raises(CustomException) as exc:
        await UserService(repo, social_service=social).delete_account("user-1", "someone@else.com")
    assert exc.value.code == "CONFIRMATION_MISMATCH"
    assert repo.deleted == [] and social.purged == []


@pytest.mark.asyncio
async def test_delete_account_removes_files_accounts_and_user(monkeypatch):
    deleted_files: list[str] = []
    monkeypatch.setattr(user_service, "_delete_user_files", lambda user_id: deleted_files.append(user_id) or 3)
    repo, social = _UserRepo(_user()), _Social()
    await UserService(repo, social_service=social).delete_account("user-1", "  ada@example.com ")
    assert deleted_files == ["user-1"]
    assert social.purged == ["user-1"]
    assert repo.deleted == ["user-1"]


@pytest.mark.asyncio
async def test_failed_file_deletion_keeps_the_account(monkeypatch):
    def fail(user_id):
        raise CustomException(message="S3 down", code="AWS_S3_ERROR")

    monkeypatch.setattr(user_service, "_delete_user_files", fail)
    repo, social = _UserRepo(_user()), _Social()
    with pytest.raises(CustomException):
        await UserService(repo, social_service=social).delete_account("user-1", "ada@example.com")
    assert repo.deleted == [] and social.purged == []


def test_user_files_are_deleted_under_every_user_prefix(monkeypatch):
    calls: list[str] = []

    class _S3:
        def delete_prefix(self, bucket, prefix):
            calls.append(prefix)
            return 1

    monkeypatch.setattr(user_service, "S3", _S3)
    assert user_service._delete_user_files("user-1") == len(user_service.USER_FILE_PREFIXES)
    assert all(prefix.endswith("/user-1/") for prefix in calls)


# -- sign-up consent --------------------------------------------------------


class _OAuth:
    async def verify_google(self, code, redirect_uri):
        return {"sub": "google-1", "email": "new@example.com", "name": "New"}


class _AuthRepo:
    def __init__(self) -> None:
        self.created: list[str] = []

    async def get_account(self, provider, provider_user_id):
        return None

    async def get_user_by_email(self, email):
        return None

    async def create_oauth_user(self, email, full_name=None, avatar_url=None):
        self.created.append(email)
        return SimpleNamespace(id="user-new")


@pytest.mark.asyncio
async def test_new_google_account_requires_terms_acceptance():
    repo = _AuthRepo()
    with pytest.raises(CustomException) as exc:
        await AuthService(repo, _OAuth()).oauth_login("google", "code", "https://app/login/google")
    assert exc.value.code == "TERMS_NOT_ACCEPTED"
    assert repo.created == []
