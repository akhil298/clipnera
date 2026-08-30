from __future__ import annotations

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import engine, Base
from auth.model import User, UserAccount, Tenant


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
