from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User, UserAccount, AuthProvider
from core.exceptions import CustomException
from core.security import hash_password

if TYPE_CHECKING:
    from auth.schemas import RegisterRequest


class UserRepository:
    """Data access layer for users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_account(self, provider: AuthProvider, provider_user_id: str) -> UserAccount | None:
        stmt = (
            select(UserAccount)
            .where(
                UserAccount.provider == provider,
                UserAccount.provider_user_id == provider_user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user_with_password(self, data: "RegisterRequest") -> User:
        hashed = await asyncio.to_thread(hash_password, data.password)

        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
        )
        self._session.add(user)
        await self._session.flush()

        account = UserAccount(
            user_id=user.id,
            provider=AuthProvider.PASSWORD,
            provider_user_id=data.email,
            password_hash=hashed,
        )
        self._session.add(account)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_oauth_user(
        self, email: str, full_name: str | None = None, avatar_url: str | None = None
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            is_verified=True,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def create_password_account(self, user_id: str, email: str) -> UserAccount:
        account = UserAccount(
            user_id=user_id,
            provider=AuthProvider.PASSWORD,
            provider_user_id=email,
        )
        self._session.add(account)
        await self._session.flush()
        return account

    async def link_oauth_account(
        self,
        user_id: str,
        provider: AuthProvider,
        provider_user_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
    ) -> UserAccount:
        account = UserAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )
        self._session.add(account)
        await self._session.commit()
        await self._session.refresh(account)
        return account

    async def update_password(self, account: UserAccount, new_password: str) -> None:
        account.password_hash = await asyncio.to_thread(hash_password, new_password)
        await self._session.commit()
