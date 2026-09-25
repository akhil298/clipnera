from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import CustomException
from core.logging_config import get_logger
from feature_flags.model import FeatureFlag
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

    async def effective(self) -> dict[str, bool]:
        return resolve(await self.stored())

    async def is_enabled(self, key: str) -> bool:
        if key not in FLAGS:
            raise KeyError(f"Undeclared feature flag {key!r}")
        return (await self.effective())[key]

    async def require(self, *keys: str) -> None:
        """403 FEATURE_DISABLED unless every flag in ``keys`` is on."""
        effective = await self.effective()
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

    async def rows(self) -> dict[str, FeatureFlag]:
        result = await self._session.execute(select(FeatureFlag))
        return {row.key: row for row in result.scalars().all()}

    async def admin_list(self) -> AdminFeatureFlagListResponse:
        """Every declared flag with its stored and effective state."""
        rows = await self.rows()
        effective = resolve({key: row.enabled for key, row in rows.items()})
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
                )
                for flag in FLAGS.values()
            ]
        )
