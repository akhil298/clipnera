"""Sign-in for the Clipnera Studio Mac app.

The app opens Google in the system browser. Google returns to the API's callback, which sends the
browser on to a port the app listens on at 127.0.0.1 with a one-time code. The app trades that code
for a session with the PKCE verifier only it holds, so a code caught by another program is useless.

Nothing is stored between the steps: the sign-in state and the one-time code are short-lived JWTs
signed with a key derived from SECRET_KEY, so neither can ever pass as an access token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from jose import JWTError, jwt

from core.config import get_settings
from core.security import ALGORITHM

settings = get_settings()

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
APP_HOST = "127.0.0.1"
STATE_TTL = timedelta(minutes=10)
CODE_TTL = timedelta(minutes=2)
_STATE = "desktop_state"
_CODE = "desktop_code"


@dataclass(frozen=True)
class DesktopState:
    code_challenge: str
    redirect_port: int
    accept_terms: bool


def _key() -> str:
    return hmac.new(settings.SECRET_KEY.encode(), b"clipnera-desktop-login", hashlib.sha256).hexdigest()


def _encode(claims: dict, ttl: timedelta) -> str:
    return jwt.encode({**claims, "exp": datetime.now(timezone.utc) + ttl}, _key(), algorithm=ALGORITHM)


def _decode(token: str, typ: str) -> dict | None:
    try:
        claims = jwt.decode(token, _key(), algorithms=[ALGORITHM])
    except JWTError:
        return None
    return claims if claims.get("typ") == typ else None


def callback_url() -> str:
    """Where Google returns; must be listed for the Google OAuth client in the Google Cloud console."""
    return f"{settings.PUBLIC_API_URL.rstrip('/')}/api/v1/auth/desktop/callback"


def authorize_url(state: DesktopState) -> str:
    token = _encode(
        {"typ": _STATE, "cc": state.code_challenge, "port": state.redirect_port, "terms": state.accept_terms},
        STATE_TTL,
    )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": token,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


def read_state(token: str) -> DesktopState | None:
    claims = _decode(token, _STATE)
    if not claims:
        return None
    return DesktopState(code_challenge=claims["cc"], redirect_port=claims["port"], accept_terms=claims["terms"])


def app_redirect(port: int, **params: str) -> str:
    return f"http://{APP_HOST}:{port}/callback?{urlencode(params)}"


def issue_code(user_id: str, code_challenge: str) -> str:
    return _encode({"typ": _CODE, "sub": user_id, "cc": code_challenge}, CODE_TTL)


def pkce_challenge(verifier: str) -> str:
    """S256: base64url(sha256(verifier)) without padding."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def redeem_code(code: str, verifier: str) -> str | None:
    """The user id when the code is valid and the verifier matches its challenge."""
    claims = _decode(code, _CODE)
    if not claims or not hmac.compare_digest(pkce_challenge(verifier), claims["cc"]):
        return None
    return claims["sub"]
