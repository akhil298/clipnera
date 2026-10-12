from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import CustomException
from core.logging_config import get_logger
from auth.model import User
from feature_flags.model import FeatureFlag, FeatureFlagUser
from feature_flags.registry import FLAGS
from feature_flags.schema import AdminFeatureFlagListResponse, AdminFeatureFlagResponse

log = get_logger(__name__)


def resolve(stored: dict[str, bool]) -> dict[str, bool]:
    """Effective state of every declared flag: stored value, and parent on."""
    effective: dict[str, bool] = {}
    for key, flag in FLAGS.items():
        on = stored.get(key, False)
        if flag.parent is not None:
            on = on and stored.get(flag.parent, False)
        effective[key] = on
    return effective


class FeatureFlagService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def stored(self) -> dict[str, bool]:
        result = await self._session.execute(select(FeatureFlag.key, FeatureFlag.enabled))
        return {key: enabled for key, enabled in result.all() if key in FLAGS}

    async def effective(self, user_id: str | None = None) -> dict[str, bool]:
        """Every flag's state; with ``user_id``, also on where that user is a test user (staged rollout)."""
        stored = await self.stored()
        if user_id:
            for key in await self._session.scalars(select(FeatureFlagUser.key).where(FeatureFlagUser.user_id == user_id)):
                if key in FLAGS:
                    stored[key] = True
        return resolve(stored)

    async def is_enabled(self, key: str) -> bool:
        if key not in FLAGS:
            raise KeyError(f"Undeclared feature flag {key!r}")
        return (await self.effective())[key]

    async def require(self, *keys: str, user_id: str | None = None) -> None:
        """403 FEATURE_DISABLED unless every flag in ``keys`` is on (for ``user_id``, when given)."""
        effective = await self.effective(user_id)
        for key in keys:
            if not effective[key]:
                raise CustomException(
                    message=f"{FLAGS[key].label} is not available right now.",
                    code="FEATURE_DISABLED",
                    status_code=403,
                    extra={"feature": key},
                )

    async def set(self, key: str, enabled: bool, admin_id: str) -> None:
        if key not in FLAGS:
            raise CustomException(message="Unknown feature flag", code="NOT_FOUND", status_code=404)
        now = datetime.utcnow()
        stmt = pg_insert(FeatureFlag).values(key=key, enabled=enabled, updated_by=admin_id, updated_at=now)
        stmt = stmt.on_conflict_do_update(
            index_elements=[FeatureFlag.key],
            set_={"enabled": enabled, "updated_by": admin_id, "updated_at": now},
        )
        await self._session.execute(stmt)
        await self._session.commit()
        log.info(f"Feature flag {key} set to {enabled} by admin={admin_id}")

    async def test_users(self) -> dict[str, list[str]]:
        """Flag key -> the emails it is on for ahead of everyone."""
        result = await self._session.execute(
            select(FeatureFlagUser.key, User.email).join(User, User.id == FeatureFlagUser.user_id).order_by(User.email)
        )
        users: dict[str, list[str]] = {}
        for key, email in result.all():
            users.setdefault(key, []).append(email)
        return users

    async def set_test_user(self, key: str, email: str, allowed: bool, admin_id: str) -> None:
        if key not in FLAGS:
            raise CustomException(message="Unknown feature flag", code="NOT_FOUND", status_code=404)
        user = await self._session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
        if user is None:
            raise CustomException(message=f"No account uses {email}.", code="USER_NOT_FOUND", status_code=404)
        row = await self._session.get(FeatureFlagUser, (key, user.id))
        if allowed and row is None:
            self._session.add(FeatureFlagUser(key=key, user_id=user.id, added_by=admin_id))
        elif not allowed and row is not None:
            await self._session.delete(row)
        await self._session.commit()
        log.info(f"Feature flag {key} {'on' if allowed else 'off'} for user={user.id} by admin={admin_id}")

    async def rows(self) -> dict[str, FeatureFlag]:
        result = await self._session.execute(select(FeatureFlag))
        return {row.key: row for row in result.scalars().all()}

    async def admin_list(self) -> AdminFeatureFlagListResponse:
        """Every declared flag with its stored and effective state."""
        rows = await self.rows()
        effective = resolve({key: row.enabled for key, row in rows.items()})
        test_users = await self.test_users()
        return AdminFeatureFlagListResponse(
            flags=[
                AdminFeatureFlagResponse(
                    key=flag.key,
                    label=flag.label,
                    description=flag.description,
                    parent=flag.parent,
                    enabled=bool(rows.get(flag.key) and rows[flag.key].enabled),
                    effective=effective[flag.key],
                    updated_at=rows[flag.key].updated_at if flag.key in rows else None,
                    test_users=test_users.get(flag.key, []),
                )
                for flag in FLAGS.values()
            ]
        )
