"""Stock sources the ingest job may pull from, chosen by BROLL_SOURCES."""

from __future__ import annotations

from broll.sources.base import StockClip, StockSource
from broll.sources.nasa import NasaSource
from broll.sources.pexels import PexelsSource
from broll.sources.pixabay import PixabaySource
from broll.sources.wikimedia import WikimediaSource
from core.config import get_settings

SOURCES: dict[str, type] = {
    "pexels": PexelsSource,
    "pixabay": PixabaySource,
    "nasa": NasaSource,
    "wikimedia": WikimediaSource,
}


def enabled_sources(names: list[str] | None = None) -> list[StockSource]:
    """Configured sources, or the named subset of them; unknown names are ignored."""
    configured = [n.strip() for n in get_settings().BROLL_SOURCES.split(",") if n.strip() in SOURCES]
    chosen = [n for n in (names or configured) if n in configured]
    return [SOURCES[name]() for name in chosen]


__all__ = ["StockClip", "StockSource", "enabled_sources", "SOURCES"]
