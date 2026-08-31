from __future__ import annotations

import asyncio

from migrate import run_migrations


async def init_db() -> None:
    """Apply all pending migrations and create tables if needed."""
    await run_migrations()
    print("Database initialized and migrations applied.")


async def main() -> None:
    await init_db()


if __name__ == "__main__":
    asyncio.run(main())
