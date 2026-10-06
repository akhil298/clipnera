"""Referrals: a user shares a code, a new user signs up with it, and both earn
bonus credits as the new user reaches each milestone in time.

    sign-up ──(pro window)──► Pro approved ──(video window)──► first video done
                               referee  +referee_pro_credits
                               referrer +referrer_pro_credits   referrer +referrer_video_credits
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ReferralStatus(str, enum.Enum):
    # Waiting for the referred user to buy Pro.
    PENDING_PRO = "pending_pro"
    # Paid in time; waiting for an admin to approve the payment.
    AWAITING_APPROVAL = "awaiting_approval"
    # Pro bought in time; waiting for the first video.
    PENDING_VIDEO = "pending_video"
    # Both milestones reached: every reward earned.
    SUCCEEDED = "succeeded"
    # Pro bought in time but no video in time: the Pro rewards are kept.
    PARTIAL = "partial"
    # Ended before any reward was earned, or the Pro payment was reversed.
    FAILED = "failed"
    # Ended by an admin, or because the referrer can no longer take part.
    VOID = "void"


OPEN_STATUSES = (ReferralStatus.PENDING_PRO, ReferralStatus.AWAITING_APPROVAL, ReferralStatus.PENDING_VIDEO)


class FailReason(str, enum.Enum):
    PRO_NOT_BOUGHT = "pro_not_bought"
    PAYMENT_REJECTED = "payment_rejected"
    APPROVAL_TIMEOUT = "approval_timeout"
    NO_VIDEO = "no_video"
    PAYMENT_REVERSED = "payment_reversed"
    ACCOUNT_DELETED = "account_deleted"
    REFERRER_UNAVAILABLE = "referrer_unavailable"
    VOIDED_BY_ADMIN = "voided_by_admin"


class ReviewState(str, enum.Enum):
    # No sign of abuse: rewards are given as they are earned.
    CLEAR = "clear"
    # Looks like the referrer's own second account: rewards wait for an admin.
    HELD = "held"
    APPROVED = "approved"


class RewardKind(str, enum.Enum):
    REFEREE_PRO = "referee_pro"
    REFERRER_PRO = "referrer_pro"
    REFERRER_VIDEO = "referrer_video"


class ReferralCode(Base):
    """A user's own code, made the first time they open their referral page."""

    __tablename__ = "referral_codes"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        Index("ix_referrals_referrer_created", "referrer_id", "created_at"),
        Index("ix_referrals_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # Null once that account is deleted; the row stays so the other side still
    # sees how the referral ended.
    referrer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    referee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    # Shown to the referrer: a first name and initial, and a masked email.
    referee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    referee_email_masked: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReferralStatus.PENDING_PRO.value)
    fail_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # The program settings when the referral began. Later changes to the
    # settings never change what an existing referral was promised.
    rules: Mapped[dict] = mapped_column(JSON, nullable=False)

    signed_up_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pro_deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pro_payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pro_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pro_activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    video_deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    video_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    video_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    video_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    review_state: Mapped[str] = mapped_column(String(10), nullable=False, default=ReviewState.CLEAR.value)
    flagged_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pro_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    video_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ReferralReward(Base):
    """One reward paid for one referral. Unique per kind, so no milestone can
    ever be paid twice, whatever runs the check and however often."""

    __tablename__ = "referral_rewards"
    __table_args__ = (UniqueConstraint("referral_id", "kind", name="uq_referral_rewards_referral_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    referral_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("referrals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    grant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credit_grants.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReferredEmail(Base):
    """A one-way hash of every email that was ever referred, kept after the
    account is deleted, so deleting and signing up again cannot earn twice."""

    __tablename__ = "referred_emails"

    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReferralSettings(Base):
    """The program's rules, changed by admins without a deploy. One row."""

    __tablename__ = "referral_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_referral_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    referee_pro_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    referrer_pro_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    referrer_video_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_expiry_days: Mapped[int] = mapped_column(Integer, nullable=False)
    pro_window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    video_window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    min_video_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_wait_days: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReferralSettingsChange(Base):
    """Who changed which setting, from what to what."""

    __tablename__ = "referral_settings_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    admin_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
