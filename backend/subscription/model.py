from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, String, Integer, Text, Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class PlanSlug(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    PRO_PLUS = "pro_plus"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PENDING = "pending"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"


class BillingPeriod(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[PlanSlug] = mapped_column(
        Enum(PlanSlug, values_callable=lambda obj: [e.value for e in obj], name='plan_slug'),
        unique=True,
        nullable=False,
    )
    credit_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # What the plan costs through UPI. Unset means the plan cannot be bought that way.
    price_inr: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    features: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    subscriptions: Mapped[list["UserSubscription"]] = relationship(
        "UserSubscription", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )
    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        "PaymentTransaction", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, values_callable=lambda obj: [e.value for e in obj], name='subscription_status'),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions", lazy="selectin")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_transactions_status_created_at", "status", "created_at"),
        CheckConstraint(
            "(plan_id IS NOT NULL AND plan_type IS NOT NULL AND credit_pack IS NULL AND credits IS NULL)"
            " OR (plan_id IS NULL AND plan_type IS NULL AND credit_pack IS NOT NULL AND credits > 0)",
            name="ck_payment_transactions_plan_or_credit_pack",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # A payment buys either a plan period (plan_id, plan_type) or a credit pack
    # (credit_pack, credits); the check constraint enforces exactly one.
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    credit_pack: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Credits granted on approval, fixed at purchase so a later price change
    # does not alter what was bought.
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, values_callable=lambda obj: [e.value for e in obj], name='payment_status'),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    payment_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which period was bought; approval extends the plan by that period's days.
    plan_type: Mapped[BillingPeriod | None] = mapped_column(
        Enum(BillingPeriod, values_callable=lambda obj: [e.value for e in obj], name="billing_period"),
        nullable=True,
    )
    # Unique so one bank transfer cannot be claimed twice.
    utr_number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    # S3 key of the payment proof; served only through short-lived signed URLs.
    screenshot_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    plan: Mapped["Plan | None"] = relationship("Plan", back_populates="transactions", lazy="selectin")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (Index("ix_credit_ledger_reference_type_created_at", "reference_type", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Total balance after this entry, bought credits included.
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # The part of balance_after that was bought: it survives cycle resets and is
    # spent only once the plan's allowance runs out.
    purchased_balance_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # How this entry changed the bought part, so a refund can return it there.
    purchased_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # The part of balance_after that is bonus credits (see CreditGrant), and how
    # this entry changed it. Like the bought part, it survives cycle resets.
    bonus_balance_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bonus_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # The admin who made a manual adjustment; null for system entries.
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by], lazy="selectin")


class CreditGrant(Base):
    """Bonus credits given for a reason (a referral reward) that expire on a date.

    Each grant keeps its own remaining amount, so credits given on different
    days expire on their own dates. Spending, refunds and expiry change
    ``remaining`` together with a ledger entry, under the user's balance lock.
    """

    __tablename__ = "credit_grants"
    __table_args__ = (
        CheckConstraint("remaining >= 0 AND remaining <= amount", name="ck_credit_grants_remaining"),
        Index("ix_credit_grants_user_open", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    # What the grant was for, e.g. "referral_referrer_pro"; reference_id names
    # the record behind it (the referral).
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Set when the leftover was removed for good: on expiry, or by an admin.
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CreditGrantSpend(Base):
    """How much of a grant one ledger entry used (positive) or gave back
    (negative), so a refund returns bonus credits to the grant they came from."""

    __tablename__ = "credit_grant_spends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    ledger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credit_ledger.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credit_grants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)


class UsageTracking(Base):
    """A per-user counter for one feature in one period.

    Daily limits keep one row per UTC day. Credit resets claim a row per cycle
    (keys ``credit_refill:*``) so a reset can only ever be applied once.
    """

    __tablename__ = "usage_tracking"
    __table_args__ = (
        UniqueConstraint("user_id", "feature_key", "period_start", name="uq_usage_tracking_user_feature_period"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
