"""A disposable Postgres for credit and referral tests.

Used by the *_db test modules, which are skipped unless TEST_DATABASE_URL
points at a database that can be wiped, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/clipnera_test pytest tests/test_credit_at_submit_db.py

Every table in it is dropped and recreated per test.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main  # noqa: F401  registers every model on Base.metadata
from auth.model import User
from core.database import Base
from subscription.model import Plan, PlanSlug
from subscription.service import SubscriptionService

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
requires_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all([
            Plan(id="plan-free", name="Free", slug=PlanSlug.FREE, credit_minutes=20, price_monthly=0),
            Plan(id="plan-pro", name="Pro", slug=PlanSlug.PRO, credit_minutes=600, price_monthly=0, price_inr=699),
        ])
        await session.commit()
    yield session_maker
    await engine.dispose()


async def new_user(maker, email: str, age_days: int = 0) -> str:
    """A Free user with their starting credits."""
    async with maker() as session:
        user = User(email=email, created_at=datetime.utcnow() - timedelta(days=age_days))
        session.add(user)
        await session.commit()
        await SubscriptionService.for_session(session).activate_free_plan(user.id)
        return user.id


async def balance(maker, user_id: str) -> int:
    async with maker() as session:
        return (await SubscriptionService.for_session(session).get_plan_summary(user_id)).credit_minutes_remaining
