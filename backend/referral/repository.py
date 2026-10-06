from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from auth.model import LoginEvent, User
from clip.model import VideoProject
from pipeline.model import PipelineState
from referral.model import (
    OPEN_STATUSES,
    Referral,
    ReferralCode,
    ReferralReward,
    ReferralSettings,
    ReferralSettingsChange,
    ReferredEmail,
)
from subscription.entitlements import PURCHASABLE_PLAN
from subscription.model import CreditGrant, PaymentTransaction, Plan


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def lock(self, key: str) -> None:
        """Serialise work on ``key`` until this transaction ends."""
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))

    # Settings

    async def settings(self) -> ReferralSettings | None:
        return await self._session.get(ReferralSettings, 1)

    async def save_settings(self, row: ReferralSettings, change: ReferralSettingsChange) -> None:
        self._session.add_all([row, change])
        await self._session.commit()

    async def settings_changes(self, limit: int) -> list[tuple[ReferralSettingsChange, str | None]]:
        stmt = (
            select(ReferralSettingsChange, User.email)
            .outerjoin(User, User.id == ReferralSettingsChange.admin_id)
            .order_by(desc(ReferralSettingsChange.created_at))
            .limit(limit)
        )
        return [(change, email) for change, email in (await self._session.execute(stmt)).all()]

    # Codes

    async def code_of(self, user_id: str) -> ReferralCode | None:
        return await self._session.get(ReferralCode, user_id)

    async def find_code(self, code: str) -> ReferralCode | None:
        return await self._session.scalar(select(ReferralCode).where(ReferralCode.code == code))

    async def add_code(self, user_id: str, code: str) -> ReferralCode:
        row = ReferralCode(user_id=user_id, code=code)
        self._session.add(row)
        await self._session.commit()
        return row

    # Referrals

    async def get(self, referral_id: str, for_update: bool = False) -> Referral | None:
        stmt = select(Referral).where(Referral.id == referral_id)
        if for_update:
            stmt = stmt.with_for_update()
        return await self._session.scalar(stmt)

    async def for_referee(self, user_id: str) -> Referral | None:
        return await self._session.scalar(select(Referral).where(Referral.referee_id == user_id))

    async def for_referrer(self, user_id: str, limit: int) -> list[Referral]:
        stmt = (
            select(Referral)
            .where(Referral.referrer_id == user_id)
            .order_by(desc(Referral.created_at))
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_since(self, referrer_id: str, since: datetime) -> int:
        stmt = select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id, Referral.created_at >= since
        )
        return int(await self._session.scalar(stmt) or 0)

    async def open_ids(self, limit: int) -> list[str]:
        stmt = (
            select(Referral.id)
            .where(Referral.status.in_([s.value for s in OPEN_STATUSES]))
            .order_by(Referral.updated_at)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def open_ids_for(self, user_id: str) -> list[str]:
        """Open referrals the user is on either side of."""
        stmt = select(Referral.id).where(
            or_(Referral.referrer_id == user_id, Referral.referee_id == user_id),
            Referral.status.in_([s.value for s in OPEN_STATUSES]),
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def ids_for(self, user_id: str) -> list[str]:
        stmt = select(Referral.id).where(or_(Referral.referrer_id == user_id, Referral.referee_id == user_id))
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, referral: Referral) -> None:
        self._session.add(referral)
        await self._session.flush()

    async def admin_search(
        self, status: str | None, review_state: str | None, query: str | None, limit: int, offset: int
    ) -> list[tuple[Referral, str | None, str | None]]:
        referrer, referee = aliased(User), aliased(User)
        stmt = (
            select(Referral, referrer.email, referee.email)
            .outerjoin(referrer, referrer.id == Referral.referrer_id)
            .outerjoin(referee, referee.id == Referral.referee_id)
        )
        if status:
            stmt = stmt.where(Referral.status == status)
        if review_state:
            stmt = stmt.where(Referral.review_state == review_state)
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(referrer.email).like(like),
                    func.lower(referee.email).like(like),
                    func.lower(Referral.code).like(like),
                )
            )
        stmt = stmt.order_by(desc(Referral.created_at)).limit(limit).offset(offset)
        return [tuple(row) for row in (await self._session.execute(stmt)).all()]

    # Abuse checks

    async def email_was_referred(self, email_hash: str) -> bool:
        return await self._session.get(ReferredEmail, email_hash) is not None

    async def remember_email(self, email_hash: str) -> None:
        self._session.add(ReferredEmail(email_hash=email_hash))
        await self._session.flush()

    async def login_ips(self, user_id: str, since: datetime) -> set[str]:
        stmt = select(LoginEvent.ip).where(
            LoginEvent.user_id == user_id, LoginEvent.created_at >= since, LoginEvent.ip.is_not(None)
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def other_referee_ips(self, referrer_id: str, exclude_user_id: str, since: datetime) -> set[str]:
        """Sign-in IPs of everyone else this referrer brought in recently."""
        stmt = (
            select(LoginEvent.ip)
            .join(Referral, Referral.referee_id == LoginEvent.user_id)
            .where(
                Referral.referrer_id == referrer_id,
                Referral.referee_id != exclude_user_id,
                LoginEvent.created_at >= since,
                LoginEvent.ip.is_not(None),
            )
        )
        return set((await self._session.execute(stmt)).scalars().all())

    # Milestones

    async def pro_payments(self, user_id: str) -> list[PaymentTransaction]:
        """The user's payments for the Pro plan (not credit packs), oldest first."""
        stmt = (
            select(PaymentTransaction)
            .join(Plan, Plan.id == PaymentTransaction.plan_id)
            .where(
                PaymentTransaction.user_id == user_id,
                PaymentTransaction.credit_pack.is_(None),
                Plan.slug == PURCHASABLE_PLAN,
            )
            .order_by(PaymentTransaction.created_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def runs_started_between(
        self, user_id: str, start: datetime, end: datetime, min_seconds: int
    ) -> list[tuple[PipelineState, VideoProject]]:
        """First runs (a resume keeps its run) of the user's videos of at least
        ``min_seconds``, started in [start, end], oldest first."""
        stmt = (
            select(PipelineState, VideoProject)
            .join(VideoProject, VideoProject.id == PipelineState.project_id)
            .where(
                VideoProject.user_id == user_id,
                VideoProject.duration_seconds >= min_seconds,
                PipelineState.created_at >= start,
                PipelineState.created_at <= end,
            )
            .order_by(PipelineState.created_at)
        )
        return [tuple(row) for row in (await self._session.execute(stmt)).all()]

    # Rewards

    async def add_reward(self, reward: ReferralReward) -> None:
        self._session.add(reward)
        await self._session.flush()

    async def rewards(self, referral_ids: list[str]) -> list[tuple[ReferralReward, CreditGrant]]:
        if not referral_ids:
            return []
        stmt = (
            select(ReferralReward, CreditGrant)
            .join(CreditGrant, CreditGrant.id == ReferralReward.grant_id)
            .where(ReferralReward.referral_id.in_(referral_ids))
            .order_by(ReferralReward.created_at)
        )
        return [tuple(row) for row in (await self._session.execute(stmt)).all()]

    async def user(self, user_id: str | None) -> User | None:
        return await self._session.get(User, user_id) if user_id else None
