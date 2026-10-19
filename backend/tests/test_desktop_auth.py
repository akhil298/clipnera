"""Clipnera Studio for Mac sign-in: Google in the browser, back to the app's 127.0.0.1 port, PKCE exchange."""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from auth import desktop
from auth.dependencies import get_auth_service
from auth.model import AuthProvider
from auth.route import auth as auth_router
from auth.service import AuthService
from core.exceptions import CustomException
from core.security import create_access_token, decode_access_token

VERIFIER = "clipnera-test-verifier_0123456789.abcdefghijk~"
# S256 worked out independently of auth.desktop.
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
PORT = 53682


class FakeRepo:
    def __init__(self, active: bool = True) -> None:
        self.user = SimpleNamespace(id="user-1", is_active=active)
        self.logins: list[tuple] = []

    async def get_user_by_id(self, user_id: str):
        return self.user if user_id == self.user.id else None

    async def add_login_event(self, user_id, method, ip, user_agent) -> None:
        self.logins.append((user_id, method, ip, user_agent))


def service(repo: FakeRepo | None = None, resolve=None) -> AuthService:
    svc = AuthService(repo or FakeRepo(), oauth_service=None)  # type: ignore[arg-type]

    async def default_resolve(provider, code, redirect_uri, accept_terms):
        assert (provider, redirect_uri) == ("google", desktop.callback_url())
        return "user-1", AuthProvider.GOOGLE

    svc._resolve_oauth_user = resolve or default_resolve  # type: ignore[method-assign]
    return svc


def state_token(accept_terms: bool = True) -> str:
    url = desktop.authorize_url(desktop.DesktopState(CHALLENGE, PORT, accept_terms))
    return parse_qs(urlparse(url).query)["state"][0]


def query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


# ── Tokens ──


def test_pkce_challenge_is_s256():
    assert desktop.pkce_challenge(VERIFIER) == CHALLENGE
    assert len(CHALLENGE) == 43


def test_authorize_url_asks_google_to_return_to_the_api():
    url = urlparse(desktop.authorize_url(desktop.DesktopState(CHALLENGE, PORT, True)))
    params = query(url.geturl())
    assert url.netloc == "accounts.google.com"
    assert params["redirect_uri"].endswith("/api/v1/auth/desktop/callback")
    assert params["scope"] == "openid email profile"
    assert desktop.read_state(params["state"]) == desktop.DesktopState(CHALLENGE, PORT, True)


def test_state_rejects_access_tokens_tampering_and_expiry(monkeypatch):
    assert desktop.read_state(create_access_token("user-1")) is None
    assert desktop.read_state(state_token()[:-2] + "xx") is None
    monkeypatch.setattr(desktop, "STATE_TTL", timedelta(seconds=-1))
    assert desktop.read_state(state_token()) is None


def test_code_redeems_only_with_the_matching_verifier():
    code = desktop.issue_code("user-1", CHALLENGE)
    assert desktop.redeem_code(code, VERIFIER) == "user-1"
    assert desktop.redeem_code(code, "x" * 43) is None
    # A sign-in state is not a code, and a code is never an access token.
    assert desktop.redeem_code(state_token(), VERIFIER) is None
    assert decode_access_token(code) is None


def test_expired_code_is_refused(monkeypatch):
    monkeypatch.setattr(desktop, "CODE_TTL", timedelta(seconds=-1))
    assert desktop.redeem_code(desktop.issue_code("user-1", CHALLENGE), VERIFIER) is None


# ── Service ──


@pytest.mark.asyncio
async def test_callback_sends_the_browser_to_the_app_with_a_code():
    url = await service().desktop_callback(state_token(), "google-code", None)
    assert url.startswith(f"http://127.0.0.1:{PORT}/callback?")
    assert desktop.redeem_code(query(url)["code"], VERIFIER) == "user-1"


@pytest.mark.asyncio
async def test_callback_passes_accept_terms_through():
    seen = {}

    async def resolve(provider, code, redirect_uri, accept_terms):
        seen["terms"] = accept_terms
        return "user-1", AuthProvider.GOOGLE

    await service(resolve=resolve).desktop_callback(state_token(accept_terms=False), "google-code", None)
    assert seen["terms"] is False


@pytest.mark.asyncio
async def test_callback_reports_cancel_and_sign_in_errors_to_the_app():
    cancelled = await service().desktop_callback(state_token(), None, "access_denied")
    assert query(cancelled) == {"error": "Google sign-in was cancelled."}

    async def refuse(*_):
        raise CustomException("Confirm you are 18 or older", code="TERMS_NOT_ACCEPTED", status_code=400)

    refused = await service(resolve=refuse).desktop_callback(state_token(), "google-code", None)
    assert query(refused) == {"error": "Confirm you are 18 or older", "error_code": "TERMS_NOT_ACCEPTED"}


@pytest.mark.asyncio
async def test_callback_with_a_bad_state_raises():
    with pytest.raises(CustomException) as exc:
        await service().desktop_callback("not-a-state", "google-code", None)
    assert exc.value.code == "DESKTOP_STATE_INVALID"


@pytest.mark.asyncio
async def test_exchange_starts_a_session_and_records_the_login():
    repo = FakeRepo()
    token = await service(repo).desktop_exchange(desktop.issue_code("user-1", CHALLENGE), VERIFIER)
    assert decode_access_token(token.access_token)["sub"] == "user-1"
    assert repo.logins == [("user-1", "google", None, None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("repo", [FakeRepo(active=False), FakeRepo()])
async def test_exchange_refuses_disabled_users_and_wrong_verifiers(repo):
    verifier = VERIFIER if not repo.user.is_active else "y" * 43
    with pytest.raises(CustomException) as exc:
        await service(repo).desktop_exchange(desktop.issue_code("user-1", CHALLENGE), verifier)
    assert exc.value.code == "DESKTOP_CODE_INVALID"
    assert repo.logins == []


# ── Routes ──


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")

    @app.exception_handler(CustomException)
    async def handler(_, exc: CustomException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    async def fake_service():
        yield service()

    app.dependency_overrides[get_auth_service] = fake_service
    return TestClient(app)


def test_routes_run_the_whole_flow(client: TestClient):
    start = client.post("/api/v1/auth/desktop/start", json={"code_challenge": CHALLENGE, "redirect_port": PORT, "accept_terms": True})
    assert start.status_code == 200
    body = start.json()
    assert body["error"] is None and body["data"]["authorize_url"].startswith("https://accounts.google.com/")

    state = query(body["data"]["authorize_url"])["state"]
    callback = client.get("/api/v1/auth/desktop/callback", params={"state": state, "code": "google-code"}, follow_redirects=False)
    assert callback.status_code == 302
    code = query(callback.headers["location"])["code"]

    exchange = client.post("/api/v1/auth/desktop/exchange", json={"code": code, "code_verifier": VERIFIER})
    assert exchange.status_code == 200
    assert decode_access_token(exchange.json()["data"]["access_token"])["sub"] == "user-1"


def test_callback_with_a_bad_state_shows_a_page(client: TestClient):
    response = client.get("/api/v1/auth/desktop/callback", params={"state": "nope", "code": "x"}, follow_redirects=False)
    assert response.status_code == 400
    assert "Start again from Clipnera Studio" in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"code_challenge": "short", "redirect_port": PORT},
        {"code_challenge": CHALLENGE, "redirect_port": 80},
        {"code_challenge": CHALLENGE[:-1] + "=", "redirect_port": PORT},
    ],
)
def test_start_validates_its_input(client: TestClient, payload):
    assert client.post("/api/v1/auth/desktop/start", json=payload).status_code == 422


def test_exchange_with_a_wrong_verifier_is_refused(client: TestClient):
    code = desktop.issue_code("user-1", CHALLENGE)
    response = client.post("/api/v1/auth/desktop/exchange", json={"code": code, "code_verifier": "z" * 43})
    assert response.status_code == 400
    assert response.json()["error"] == "DESKTOP_CODE_INVALID"
