"""Download free B-roll into a local folder as short shots, each with its licence.

Uses the same stock sources and topic list as ``broll.seed`` but touches
neither S3 nor the database. Every topic runs at once; downloads are capped
per source so the hosts do not throttle or block us, and cutting is capped at
the CPU count. Each source clip is split at its shot changes into 3-8 s shots;
old, low-resolution and talking-head footage (news, interviews, lectures) is
skipped. Layout::

    <out>/CREDITS.csv                               one row per shot: licence, author, attribution
    <out>/<category>/<topic>/<shot>/<shot>.mp4      the shot (H.264, no audio)
    <out>/<category>/<topic>/<shot>/COPYRIGHT.txt   its licence, credit and source record

Clips already listed in CREDITS.csv are skipped, so a stopped run resumes.

    python -m broll.collect                              # into ./broll_library
    python -m broll.collect --out ~/broll --per-source 10 --sources nasa wikimedia
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import tempfile
from pathlib import Path

from broll import renditions
from broll.ingest import SkipClip, download, shot_ranges
from broll.seed import TOPICS
from broll.sources import StockClip, StockSource, enabled_sources
from core.config import get_settings
from core.logging_config import get_logger, setup_logging

log = get_logger(__name__)

MIN_SHOT_SECONDS = 3.0
MAX_SHOT_SECONDS = 8.0
MAX_SHOTS_PER_CLIP = 4
MAX_SOURCE_SECONDS = 600.0
MIN_YEAR = 2015
# Parallel downloads per host; Wikimedia throttles hardest.
SOURCE_CONCURRENCY = {"wikimedia": 2, "nasa": 6}
DEFAULT_SOURCE_CONCURRENCY = 4
NOT_BROLL = re.compile(
    r"\b(inside ksc|this week|news|update|interview|meet|briefing|conference|lecture|speech|talk|podcast|"
    r"hearing|statement|remarks|panel|webinar|q&a|live|trump|biden|modi|zelensk\w*|putin|president|minister)\b",
    re.I,
)
CREDITS_FIELDS = [
    "file", "category", "topic", "shot_start_s", "shot_seconds", "source", "source_id", "title", "author",
    "author_url", "license_code", "license_url", "commercial_ok", "attribution_text", "source_url",
]


def slug(text: str, limit: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].rstrip("-") or "clip"


def clip_year(clip: StockClip) -> int | None:
    """The year the clip was made, from the source's date or a year in its title."""
    dated = str(clip.record.get("date_created") or "")[:4]
    if dated.isdigit():
        return int(dated)
    years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", clip.title)]
    return min(years) if years else None


def rejection(clip: StockClip) -> str | None:
    """Why the clip's metadata rules it out before downloading, if it does."""
    settings = get_settings()
    short_side = min(clip.width, clip.height)
    if short_side and short_side < settings.BROLL_MIN_SHORT_SIDE:
        return f"{clip.width}x{clip.height} is below the resolution floor"
    if clip.duration_s > MAX_SOURCE_SECONDS:
        return f"{clip.duration_s:.0f}s source is too long to cut"
    if NOT_BROLL.search(clip.title):
        return "talking-head or news footage"
    year = clip_year(clip)
    if year and year < MIN_YEAR:
        return f"from {year}, older than {MIN_YEAR}"
    return None


def cut_cmd(src: str, out: str, start: float, duration: float) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-ss", f"{start:.3f}", "-i", src, "-t", f"{duration:.3f}", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
    ]


def copyright_text(clip: StockClip, file_name: str, start: float, duration: float) -> str:
    lines = [
        f"File:          {file_name}",
        f"Title:         {clip.title}",
        f"Cut from:      {start:.1f}s to {start + duration:.1f}s of the source video",
        f"Source:        {clip.source} ({clip.source_url})",
        f"Author:        {clip.author or 'unknown'}" + (f" ({clip.author_url})" if clip.author_url else ""),
        f"License:       {clip.license_code}" + (f" ({clip.license_url})" if clip.license_url else ""),
        f"Commercial:    {'allowed' if clip.commercial_ok else 'NOT allowed'}",
        f"Credit line:   {clip.attribution_text or 'none required'}",
        "",
        "Source record (licence evidence, as returned by the source API):",
        json.dumps(clip.record, indent=2, ensure_ascii=False, default=str),
    ]
    return "\n".join(lines) + "\n"


class Collector:
    def __init__(self, out: Path, per_source: int, sources: list[str] | None) -> None:
        self._out = out
        self._per_source = per_source
        self._sources = enabled_sources(sources)
        self._host_slots = {
            s.name: asyncio.Semaphore(SOURCE_CONCURRENCY.get(s.name, DEFAULT_SOURCE_CONCURRENCY)) for s in self._sources
        }
        self._cpu_slots = asyncio.Semaphore(os.cpu_count() or 4)
        self._credits = out / "CREDITS.csv"
        self._seen = self._load_seen()
        self.saved = self.skipped = self.failed = 0

    def _load_seen(self) -> set[tuple[str, str]]:
        if not self._credits.exists():
            return set()
        with self._credits.open(newline="") as f:
            return {(row["source"], row["source_id"]) for row in csv.DictReader(f)}

    def _record(self, row: dict[str, object]) -> None:
        new = not self._credits.exists()
        with self._credits.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CREDITS_FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)

    async def collect_topic(self, category: str, topic: str) -> None:
        folder = self._out / category / slug(topic)
        await asyncio.gather(*(self._collect_source(source, category, topic, folder) for source in self._sources))
        log.info("Done: %s / %r", category, topic)

    async def _collect_source(self, source: StockSource, category: str, topic: str, folder: Path) -> None:
        try:
            async with self._host_slots[source.name]:
                clips = await source.search(topic, self._per_source * 3)
        except Exception as exc:
            log.warning("%s search failed for %r: %s", source.name, topic, exc)
            return
        kept = 0
        for clip in clips:
            if kept >= self._per_source:
                break
            kept += await self._collect_clip(clip, category, topic, folder)

    async def _collect_clip(self, clip: StockClip, category: str, topic: str, folder: Path) -> int:
        """Shots saved from ``clip``."""
        key = (clip.source, clip.source_id)
        reason = "already collected" if key in self._seen else rejection(clip)
        if reason:
            self.skipped += 1
            log.info("Skipped %s/%s: %s", clip.source, clip.source_id, reason)
            return 0
        self._seen.add(key)
        try:
            return await self._cut_clip(clip, category, topic, folder)
        except SkipClip as skip:
            self.skipped += 1
            log.info("Skipped %s/%s: %s", clip.source, clip.source_id, skip)
        except Exception as exc:
            self.failed += 1
            log.warning("Failed %s/%s: %s", clip.source, clip.source_id, exc)
        return 0

    async def _cut_clip(self, clip: StockClip, category: str, topic: str, folder: Path) -> int:
        settings = get_settings()
        with tempfile.TemporaryDirectory() as workdir:
            source_path = Path(workdir) / "source"
            async with self._host_slots[clip.source]:
                await download(clip.download_url, source_path, settings.BROLL_MAX_DOWNLOAD_BYTES)
            info = await renditions.probe(str(source_path))
            if min(info.width, info.height) < settings.BROLL_MIN_SHORT_SIDE:
                raise SkipClip(f"{info.width}x{info.height} is below the resolution floor")
            if info.duration > MAX_SOURCE_SECONDS:
                raise SkipClip(f"{info.duration:.0f}s source is too long to cut")
            async with self._cpu_slots:
                ranges = await asyncio.to_thread(shot_ranges, str(source_path), info.duration, MIN_SHOT_SECONDS)
            shots = [(start, min(end - start, MAX_SHOT_SECONDS)) for start, end in ranges][:MAX_SHOTS_PER_CLIP]
            if not shots:
                raise SkipClip("no shot is long enough")
            stem = f"{slug(clip.title, 50)}-{clip.source}-{slug(clip.source_id, 24)}"
            for index, (start, duration) in enumerate(shots, 1):
                await self._save_shot(clip, str(source_path), f"{stem}-shot{index}", start, duration, category, topic, folder)
        return len(shots)

    async def _save_shot(
        self, clip: StockClip, source_path: str, name: str, start: float, duration: float,
        category: str, topic: str, folder: Path,
    ) -> None:
        shot_dir = folder / name
        shot_dir.mkdir(parents=True, exist_ok=True)
        video = shot_dir / f"{name}.mp4"
        async with self._cpu_slots:
            await renditions.run(cut_cmd(source_path, str(video), start, duration))
        (shot_dir / "COPYRIGHT.txt").write_text(copyright_text(clip, video.name, start, duration))
        self._record({
            "file": video.relative_to(self._out).as_posix(), "category": category, "topic": topic,
            "shot_start_s": round(start, 2), "shot_seconds": round(duration, 2),
            **{field: getattr(clip, field) for field in CREDITS_FIELDS[5:]},
        })
        self.saved += 1
        log.info("Saved %s (%.1fs, %s)", video.relative_to(self._out), duration, clip.attribution_text or clip.license_code)


async def collect(out: Path, topics: list[tuple[str, str]], per_source: int, sources: list[str] | None) -> Collector:
    collector = Collector(out, per_source, sources)
    log.info("Collecting %s topics in parallel", len(topics))
    await asyncio.gather(*(collector.collect_topic(category, topic) for category, topic in topics))
    return collector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("broll_library"), help="target folder (default ./broll_library)")
    parser.add_argument("--topics", nargs="+", help="topics to collect instead of the built-in list (saved under 'custom')")
    parser.add_argument("--per-source", type=int, default=5, help="source clips per source per topic (default 5)")
    parser.add_argument("--sources", nargs="+", help="subset of BROLL_SOURCES to use")
    args = parser.parse_args()
    setup_logging()
    topics = [("custom", t) for t in args.topics] if args.topics else [(c, t) for c, ts in TOPICS.items() for t in ts]
    out = args.out.expanduser()
    out.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(collect(out, topics, args.per_source, args.sources))
    print(f"{result.saved} shots saved to {out}, {result.skipped} clips skipped, {result.failed} failed")


if __name__ == "__main__":
    main()
