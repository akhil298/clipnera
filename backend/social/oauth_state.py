"""Single-use OAuth ``state`` values bound to the user who started the flow.

Only a SHA-256 hash of the state is stored, and the PKCE verifier is
encrypted, so a copy of this table cannot be used to finish someone's flow.
Consuming is one atomic UPDATE: a state that is missing, already used,
expired, for another platform or started by another user is rejected, and a
concurrent replay of the same state can succeed at most once.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import TokenCipher, get_token_cipher
from core.exceptions import CustomException
from social.model import OAuthState, SocialPlatform

STATE_TTL = timedelta(minutes=10)


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def _aad(state_hash: str) -> str:
    return f"oauth_states:{state_hash}:code_verifier"


@dataclass(frozen=True)
class ConsumedState:
    user_id: str
    platform: SocialPlatform
    code_verifier: str | None


def invalid_state() -> CustomException:
    # One message for every failure so the response reveals nothing about why.
    return CustomException(
        message="This connection link is invalid or has expired. Please start connecting again.",
        code="OAUTH_STATE_INVALID",
        status_code=400,
    )


class OAuthStateStore:
    def __init__(self, session: AsyncSession, cipher: TokenCipher | None = None) -> None:
        self._session = session
        self._cipher = cipher or get_token_cipher()

    async def create(self, user_id: str, platform: SocialPlatform, code_verifier: str | None) -> str:
        """Store a new state and return it. Commits."""
        state = secrets.token_urlsafe(32)
        state_hash = _hash(state)
        sealed = self._cipher.encrypt(code_verifier, _aad(state_hash)) if code_verifier else None
        self._session.add(
            OAuthState(
                state_hash=state_hash,
                code_verifier_ct=sealed.ciphertext if sealed else None,
                key_version=sealed.key_version if sealed else None,
                user_id=user_id,
                platform=platform,
                expires_at=datetime.utcnow() + STATE_TTL,
            )
        )
        await self._session.commit()
        return state

    async def consume(self, state: str, user_id: str, platform: SocialPlatform) -> ConsumedState:
        """Mark the state used and return it, or raise OAUTH_STATE_INVALID. Commits."""
        if not state or len(state) > 200:
            raise invalid_state()
        state_hash = _hash(state)
        now = datetime.utcnow()
        result = await self._session.execute(
            update(OAuthState)
            .where(
                OAuthState.state_hash == state_hash,
                OAuthState.used_at.is_(None),
                OAuthState.expires_at > now,
                OAuthState.user_id == user_id,
                OAuthState.platform == platform,
            )
            .values(used_at=now)
            .returning(OAuthState.code_verifier_ct, OAuthState.key_version)
        )
        row = result.first()
        await self._session.commit()
        if row is None:
            raise invalid_state()
        verifier_ct, key_version = row
        verifier = (
            self._cipher.decrypt(verifier_ct, key_version, _aad(state_hash)) if verifier_ct is not None else None
        )
        return ConsumedState(user_id=user_id, platform=platform, code_verifier=verifier)

    async def purge(self, older_than: timedelta = timedelta(hours=24)) -> int:
        """Delete used or expired states past ``older_than``. Commits."""
        cutoff = datetime.utcnow() - older_than
        result = await self._session.execute(
            delete(OAuthState).where(or_(OAuthState.expires_at < cutoff, OAuthState.used_at < cutoff))
        )
        await self._session.commit()
        return result.rowcount or 0
