"""The only code that reads or writes the oauth_tokens table.

Values are encrypted with core/crypto.py and bound to their account id and
field, so a ciphertext copied to another row fails to decrypt. Decryption
(``load``) is used by the publisher worker only; the API process encrypts
fresh tokens at connect time and never reads them back.
"""

from __future__ import annotations

import base64
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import TokenCipher, get_token_cipher
from social.model import OAuthToken
from social.providers.base import TokenSet


def _aad(account_id: str, field: str) -> str:
    return f"oauth_tokens:{account_id}:{field}"


def seal_text(value: str, aad: str, cipher: TokenCipher | None = None) -> str:
    """Encrypt a short value for a text column, as "<key version>:<base64>"."""
    sealed = (cipher or get_token_cipher()).encrypt(value, aad)
    return f"{sealed.key_version}:{base64.b64encode(sealed.ciphertext).decode()}"


def open_text(value: str, aad: str, cipher: TokenCipher | None = None) -> str:
    version, _, encoded = value.partition(":")
    return (cipher or get_token_cipher()).decrypt(base64.b64decode(encoded), int(version), aad)


class TokenStore:
    def __init__(self, session: AsyncSession, cipher: TokenCipher | None = None) -> None:
        self._session = session
        self._cipher = cipher or get_token_cipher()

    async def save(self, account_id: str, tokens: TokenSet) -> None:
        """Insert or replace an account's tokens. Does not commit."""
        access = self._cipher.encrypt(tokens.access_token, _aad(account_id, "access"))
        refresh = (
            self._cipher.encrypt(tokens.refresh_token, _aad(account_id, "refresh")) if tokens.refresh_token else None
        )
        values = {
            "access_token_ct": access.ciphertext,
            "refresh_token_ct": refresh.ciphertext if refresh else None,
            "access_expires_at": tokens.expires_at,
            "refresh_expires_at": tokens.refresh_expires_at,
            "key_version": access.key_version,
            "refresh_failures": 0,
            "updated_at": datetime.utcnow(),
        }
        stmt = pg_insert(OAuthToken).values(account_id=account_id, **values)
        await self._session.execute(stmt.on_conflict_do_update(index_elements=[OAuthToken.account_id], set_=values))

    async def load(self, account_id: str) -> TokenSet | None:
        row = await self._session.get(OAuthToken, account_id)
        if row is None:
            return None
        return TokenSet(
            access_token=self._cipher.decrypt(row.access_token_ct, row.key_version, _aad(account_id, "access")),
            refresh_token=(
                self._cipher.decrypt(row.refresh_token_ct, row.key_version, _aad(account_id, "refresh"))
                if row.refresh_token_ct
                else None
            ),
            expires_at=row.access_expires_at,
            refresh_expires_at=row.refresh_expires_at,
        )

    async def expiry(self, account_id: str) -> datetime | None:
        result = await self._session.execute(
            select(OAuthToken.access_expires_at).where(OAuthToken.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, account_id: str) -> None:
        """Remove an account's tokens. Does not commit."""
        await self._session.execute(delete(OAuthToken).where(OAuthToken.account_id == account_id))

    async def record_refresh_failure(self, account_id: str) -> int:
        result = await self._session.execute(
            update(OAuthToken)
            .where(OAuthToken.account_id == account_id)
            .values(refresh_failures=OAuthToken.refresh_failures + 1)
            .returning(OAuthToken.refresh_failures)
        )
        await self._session.commit()
        return result.scalar_one_or_none() or 0

    async def due_for_refresh(self, before: datetime, limit: int) -> list[str]:
        """Account ids whose access token expires before ``before``."""
        result = await self._session.execute(
            select(OAuthToken.account_id)
            .where(OAuthToken.access_expires_at.is_not(None), OAuthToken.access_expires_at < before)
            .order_by(OAuthToken.access_expires_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def stale_key_accounts(self, limit: int) -> list[str]:
        result = await self._session.execute(
            select(OAuthToken.account_id).where(OAuthToken.key_version != self._cipher.active_version).limit(limit)
        )
        return list(result.scalars().all())
