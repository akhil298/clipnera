"""Bulk-fill the B-roll library from the free stock sources.

Runs the same ingest as the admin endpoint over a list of cutaway topics, one
topic at a time so the stock hosts' rate limits hold. Every shot is stored with
the licence, author and attribution of its source clip. Clips already in the
library are skipped, so an interrupted run can simply be started again.

    python -m broll.seed                      # every topic, 5 clips per source
    python -m broll.seed --per-source 10 --sources pexels nasa
    python -m broll.seed --topics "city at night" "coffee pouring"
"""

from __future__ import annotations

import argparse
import asyncio

import auth.model  # noqa: F401  registers "users", which broll_assets.owner_user_id references
from broll.ingest import Ingestor, IngestReport
from broll.repository import BrollRepository
from core.database import AsyncSessionLocal
from core.logging_config import get_logger, setup_logging

log = get_logger(__name__)

TOPICS: dict[str, list[str]] = {
    "business": [
        "office meeting", "typing on laptop", "startup team", "handshake", "presentation whiteboard",
        "stock market chart", "counting money", "coworking space", "video call", "signing contract",
    ],
    "technology": [
        "coding on screen", "server room", "smartphone scrolling", "circuit board", "robot",
        "data center", "virtual reality headset", "drone flying", "3d printer", "social media phone",
    ],
    "city": [
        "city skyline", "city at night", "traffic timelapse", "busy street crowd", "subway train",
        "aerial city", "rain on window", "neon lights", "walking in city", "highway at night",
    ],
    "nature": [
        "ocean waves", "mountain landscape", "forest aerial", "sunrise", "sunset clouds",
        "waterfall", "desert dunes", "snow falling", "river stream", "starry night sky",
    ],
    "people": [
        "people laughing", "friends talking", "family dinner", "person thinking", "crowd cheering",
        "woman walking", "man walking", "children playing", "hands close up", "hugging",
    ],
    "health": [
        "gym workout", "running outdoors", "yoga", "healthy food", "meditation",
        "doctor hospital", "sleeping", "cycling", "swimming", "stretching",
    ],
    "food": [
        "cooking kitchen", "coffee pouring", "street food", "chopping vegetables", "restaurant",
        "baking bread", "pouring drink", "grocery shopping", "indian food", "tea",
    ],
    "lifestyle": [
        "travel airport", "road trip car", "reading book", "shopping", "home interior",
        "writing notebook", "studying", "celebration party", "wedding", "music concert",
    ],
    "abstract": [
        "abstract background", "smoke", "fire", "light leaks", "particles",
        "ink in water", "bokeh lights", "clock ticking", "hourglass", "fireworks",
    ],
    # Animated, not filmed: backdrops and accents for stats, lists and transitions.
    "motion_graphics": [
        "motion graphics background", "abstract loop animation", "animated gradient background",
        "geometric shapes animation", "glitch effect", "particles animation", "neon lines animation",
        "countdown animation", "data visualization animation", "digital grid animation",
    ],
    "science": [
        "space earth", "rocket launch", "astronaut", "planets", "laboratory",
        "microscope", "galaxy", "moon", "satellite", "solar flare",
    ],
    "india": [
        "india street", "mumbai", "delhi traffic", "indian festival", "indian market",
        "taj mahal", "kerala backwaters", "indian village", "cricket", "diwali",
    ],
}


def all_topics() -> list[str]:
    return [topic for topics in TOPICS.values() for topic in topics]


async def seed(topics: list[str], per_source: int, sources: list[str] | None) -> list[IngestReport]:
    reports: list[IngestReport] = []
    for number, topic in enumerate(topics, 1):
        log.info("Seeding topic %s/%s: %r", number, len(topics), topic)
        async with AsyncSessionLocal() as session:
            reports.append(await Ingestor(BrollRepository(session)).ingest_query(topic, per_source, sources))
    return reports


def summarise(reports: list[IngestReport]) -> str:
    added = sum(r.added for r in reports)
    skipped = sum(r.skipped for r in reports)
    failed = sum(r.failed for r in reports)
    lines = [f"{len(reports)} topics: {added} shots added, {skipped} clips skipped, {failed} failed"]
    lines += [f"  {r.query}: {error}" for r in reports for error in r.errors]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--topics", nargs="+", help="topics to ingest instead of the built-in list")
    parser.add_argument("--per-source", type=int, default=5, help="clips per source per topic (default 5)")
    parser.add_argument("--sources", nargs="+", help="subset of BROLL_SOURCES to use")
    args = parser.parse_args()
    setup_logging()
    reports = asyncio.run(seed(args.topics or all_topics(), args.per_source, args.sources))
    print(summarise(reports))


if __name__ == "__main__":
    main()
