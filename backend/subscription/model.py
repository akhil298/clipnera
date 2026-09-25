from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, Integer, Text, Boolean, DateTime, Enum, ForeignKey, Index, Numeric
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
    __table_args__ = (Index("ix_payment_transactions_status_created_at", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
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

    plan: Mapped["Plan"] = relationship("Plan", back_populates="transactions", lazy="selectin")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
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
