from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from onboarding.model import UserOnboarding


class UserRepository:
    """Access to user profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_onboarded(self, user_id: str) -> bool:
        return await self._session.get(UserOnboarding, user_id) is not None

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_plan_notice(self, user_id: str) -> None:
        await self._session.execute(update(User).where(User.id == user_id).values(plan_notice_pending=False))
        await self._session.commit()

    async def list_ids_after(self, after_id: str | None, limit: int) -> list[str]:
        """User ids in id order, for walking every account in batches."""
        stmt = select(User.id).order_by(User.id).limit(limit)
        if after_id:
            stmt = stmt.where(User.id > after_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_email_notifications(self, user_id: str, enabled: bool) -> None:
        await self._session.execute(update(User).where(User.id == user_id).values(email_notifications=enabled))
        await self._session.commit()

    async def delete(self, user_id: str) -> None:
        """Delete the user; foreign keys cascade to or detach everything they own."""
        await self._session.execute(delete(User).where(User.id == user_id))
        await self._session.commit()
