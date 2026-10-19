"""Builds the throwaway database the way backend/tests do, and makes one test user with the AI editor on and credits.

Run from backend/ with the overrides in run.sh; writes the user's session token to the path given."""
import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main  # noqa: F401  registers every model on Base.metadata
from auth.model import User
from core.config import get_settings
from core.database import Base
from core.security import create_access_token
from feature_flags.model import FeatureFlagUser
from subscription.model import Plan, PlanSlug
from subscription.service import SubscriptionService


async def run() -> None:
    engine = create_async_engine(get_settings().DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add_all([
            Plan(id="plan-free", name="Free", slug=PlanSlug.FREE, credit_minutes=20, price_monthly=0),
            Plan(id="plan-pro", name="Pro", slug=PlanSlug.PRO, credit_minutes=600, price_monthly=0, price_inr=499),
        ])
        user = User(email="e2e-creator@example.com", full_name="E2E Creator", is_verified=True)
        session.add(user)
        await session.commit()
        session.add(FeatureFlagUser(key="agent_editor", user_id=user.id))
        await session.commit()
        await SubscriptionService.for_session(session).activate_free_plan(user.id)
        await SubscriptionService.for_session(session).grant_bonus_credits(user.id, 500, 30, source="e2e", reason="End-to-end test")
    await engine.dispose()
    with open(sys.argv[1], "w") as f:
        f.write(create_access_token(user.id))
    print("user", user.id)


asyncio.run(run())
