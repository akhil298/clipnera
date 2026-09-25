from __future__ import annotations

import asyncio

from migrate import run_migrations


async def init_db() -> None:
    """Apply all pending migrations and create tables if needed."""
    await run_migrations()
    await seed_plans()
    print("Database initialized and migrations applied.")


async def seed_plans() -> None:
    from core.database import AsyncSessionLocal
    from subscription.model import Plan, PlanSlug
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan))
        existing = result.scalars().all()
        if existing:
            return

        plans = [
            Plan(
                name="Free",
                slug=PlanSlug.FREE,
                credit_minutes=60,
                price_monthly=0,
                currency="USD",
                is_active=True,
                features="60 AI Processing Minutes / mo, Auto 9:16 Reframe & Face Tracking, Hormozi & MrBeast Caption Styles, Studio Noise Cancellation",
            ),
            Plan(
                name="Pro",
                slug=PlanSlug.PRO,
                credit_minutes=600,
                price_monthly=29,
                price_inr=499,
                currency="USD",
                is_active=True,
                features="300 AI Processing Minutes / mo, Prompt-to-Shorts Story AI Generator, Full Custom Brand Kits & Watermarks, Multi-Platform Auto Scheduler, 4K 60fps Ultra HD Export",
            ),
            Plan(
                name="Pro Plus",
                slug=PlanSlug.PRO_PLUS,
                credit_minutes=1200,
                price_monthly=79,
                currency="USD",
                # No longer sold; kept for existing subscribers.
                is_active=False,
                features="1,200 AI Processing Minutes / mo, Unlimited Client Workspaces, Team Collaboration & Shared Brand Kits, Priority Rendering Pipeline",
            ),
        ]
        for plan in plans:
            session.add(plan)
        await session.commit()
        print("Seeded subscription plans.")


async def main() -> None:
    await init_db()


if __name__ == "__main__":
    asyncio.run(main())
