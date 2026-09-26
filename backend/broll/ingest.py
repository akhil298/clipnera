"""Stock clip -> library shots.

Runs offline as a queued job, never on a user's request: download the clip
(size-capped), drop duplicates by content hash, gate on quality, split into
shots, render each shot's vertical master, proxy and thumbnail, upload them,
and record the asset with the licence it was taken under.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import cv2
import httpx

from broll import renditions
from broll.embeddings import get_embedder
from broll.model import AssetKind, AssetStatus, BrollAsset, BrollLicense
from broll.repository import BrollRepository
from broll.sources import StockClip, enabled_sources
from broll.sources.base import http_client
from clients.services.s3 import S3
from core.config import get_settings
from core.logging_config import get_logger
from video_processor.editing import shot_cuts, shot_windows

log = get_logger(__name__)

SAMPLE_FPS = 2.0
MAX_SHOTS_PER_CLIP = 6
MAX_SHOT_SECONDS = 15.0
MAX_CLIP_SECONDS = 180.0
# Stock hosts rate-limit bulk downloads; ingest is a background job, so it waits.
DOWNLOAD_ATTEMPTS = 4
MAX_RETRY_WAIT_SECONDS = 60.0
PAUSE_BETWEEN_DOWNLOADS_SECONDS = 2.0


class SkipClip(Exception):
    """The clip is not usable (too small, too long, a duplicate); not an error."""


@dataclass
class IngestReport:
    query: str
    added: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def quality_score(short_side: int) -> float:
    return round(0.4 + 0.6 * min(1.0, short_side / 1080), 3)


def orientation_of(width: int, height: int) -> str:
    if abs(width - height) <= min(width, height) * 0.1:
        return "square"
    return "portrait" if height > width else "landscape"


def search_text(title: str, tags: list[str], caption: str = "") -> str:
    return " ".join(part for part in (title, caption, " ".join(tags)) if part)


def shot_ranges(path: str, duration: float, min_seconds: float) -> list[tuple[float, float]]:
    """Shot windows of the clip, each at least ``min_seconds`` and at most MAX_SHOT_SECONDS."""
    capture = cv2.VideoCapture(path)
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps / SAMPLE_FPS))

    def frames():
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                return
            if index % step == 0:
                yield index / fps, frame
            index += 1

    try:
        cuts = shot_cuts(frames())
    finally:
        capture.release()
    ranges = [(a, min(b, a + MAX_SHOT_SECONDS)) for a, b in shot_windows(0.0, duration, cuts) if b - a >= min_seconds]
    return ranges[:MAX_SHOTS_PER_CLIP]


def retry_wait(response: httpx.Response, attempt: int) -> float | None:
    """Seconds to wait before retrying a throttled download, or None when it should not be retried."""
    if response.status_code not in (429, 503) or attempt >= DOWNLOAD_ATTEMPTS:
        return None
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 5.0 * 2 ** (attempt - 1)
    return min(MAX_RETRY_WAIT_SECONDS, max(1.0, wait))


async def download(url: str, target: Path, max_bytes: int) -> str:
    """Stream ``url`` to ``target``, refusing anything over ``max_bytes``; returns its SHA-256."""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            return await _download_once(url, target, max_bytes)
        except httpx.HTTPStatusError as exc:
            wait = retry_wait(exc.response, attempt)
            if wait is None:
                raise
            log.info("Throttled by %s, retrying in %.0fs", exc.request.url.host, wait)
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")


async def _download_once(url: str, target: Path, max_bytes: int) -> str:
    digest = hashlib.sha256()
    written = 0
    async with http_client() as client, client.stream("GET", url) as response:
        response.raise_for_status()
        declared = int(response.headers.get("content-length") or 0)
        if declared > max_bytes:
            raise SkipClip(f"file is {declared // 1_000_000} MB")
        with target.open("wb") as out:
            async for chunk in response.aiter_bytes(1 << 20):
                written += len(chunk)
                if written > max_bytes:
                    raise SkipClip("file exceeds the size cap")
                digest.update(chunk)
                out.write(chunk)
    return digest.hexdigest()


async def upload_renditions(s3: S3, asset_id: str, vertical: Path, proxy: Path, thumb: Path) -> dict[str, str]:
    """Store a shot's three files; returns the asset columns that point at them."""
    settings = get_settings()
    prefix = f"{settings.BROLL_S3_PREFIX}/assets/{asset_id}"
    files = {"vertical_key": (vertical, "video/mp4"), "proxy_key": (proxy, "video/mp4"), "thumb_key": (thumb, "image/jpeg")}
    keys: dict[str, str] = {}
    for column, (path, content_type) in files.items():
        key = f"{prefix}/{path.name}"
        await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, key, str(path), content_type)
        keys[column] = key
    return keys


class Ingestor:
    def __init__(self, repo: BrollRepository, s3: S3 | None = None) -> None:
        self._repo = repo
        self._s3 = s3 or S3()
        self._settings = get_settings()
        self._embedder = get_embedder()

    async def ingest_query(self, query: str, per_source: int, source_names: list[str] | None = None) -> IngestReport:
        report = IngestReport(query=query)
        for source in enabled_sources(source_names):
            try:
                clips = await source.search(query, per_source)
            except Exception as exc:
                report.errors.append(f"{source.name}: {exc}")
                continue
            for index, clip in enumerate(clips):
                if index:
                    await asyncio.sleep(PAUSE_BETWEEN_DOWNLOADS_SECONDS)
                try:
                    report.added += await self.ingest_clip(clip)
                except SkipClip as skip:
                    report.skipped += 1
                    log.info("Skipped %s/%s: %s", clip.source, clip.source_id, skip)
                except Exception as exc:
                    report.failed += 1
                    report.errors.append(f"{clip.source}/{clip.source_id}: {exc}")
                    log.warning("Ingest failed for %s/%s: %s", clip.source, clip.source_id, exc)
        log.info("B-roll ingest %r: %s added, %s skipped, %s failed", query, report.added, report.skipped, report.failed)
        return report

    async def ingest_clip(self, clip: StockClip) -> int:
        """Shots added from ``clip``; raises SkipClip when it is not usable."""
        if await self._repo.exists(clip.source, clip.source_id):
            raise SkipClip("already in the library")
        with tempfile.TemporaryDirectory() as workdir:
            work = Path(workdir)
            source_path = work / "source"
            content_hash = await download(clip.download_url, source_path, self._settings.BROLL_MAX_DOWNLOAD_BYTES)
            if await self._repo.hash_exists(content_hash):
                raise SkipClip("duplicate of an asset from another source")
            info = await renditions.probe(str(source_path))
            short_side = min(info.width, info.height)
            if short_side < self._settings.BROLL_MIN_SHORT_SIDE:
                raise SkipClip(f"{info.width}x{info.height} is below the resolution floor")
            if not (self._settings.BROLL_MIN_SHOT_SECONDS <= info.duration <= MAX_CLIP_SECONDS):
                raise SkipClip(f"{info.duration:.0f}s is outside the usable length")
            shots = await asyncio.to_thread(shot_ranges, str(source_path), info.duration, self._settings.BROLL_MIN_SHOT_SECONDS)
            if not shots:
                raise SkipClip("no shot is long enough")

            record_key = f"{self._settings.BROLL_S3_PREFIX}/records/{clip.source}/{clip.source_id}.json"
            await asyncio.to_thread(
                self._s3.put_object, self._settings.S3_BUCKET_NAME, record_key,
                json.dumps(clip.record, ensure_ascii=False, default=str).encode(), ContentType="application/json",
            )
            text = search_text(clip.title, clip.tags)
            embedding = (await self._embedder.embed([text]))[0] if self._embedder else None
            for index, (start, end) in enumerate(shots):
                asset_id = str(uuid4())
                shot_dir = work / f"shot{index}"
                shot_dir.mkdir()
                vertical, proxy, thumb = await renditions.render_shot(str(source_path), shot_dir, start, end - start)
                keys = await upload_renditions(self._s3, asset_id, vertical, proxy, thumb)
                await self._repo.add(
                    BrollAsset(
                        id=asset_id, kind=AssetKind.STOCK, source=clip.source, source_id=clip.source_id,
                        shot_index=index, source_url=clip.source_url, title=clip.title[:300], caption="",
                        tags=[t[:80] for t in clip.tags], search_text=text, start_s=round(start, 3),
                        duration_s=round(end - start, 3), width=info.width, height=info.height,
                        orientation=orientation_of(info.width, info.height), fps=round(info.fps, 3),
                        quality_score=quality_score(short_side), status=AssetStatus.LIVE,
                        content_hash=content_hash if index == 0 else None, embedding=embedding, **keys,
                    ),
                    BrollLicense(
                        license_code=clip.license_code, license_url=clip.license_url, author=clip.author,
                        author_url=clip.author_url, attribution_text=clip.attribution_text,
                        commercial_ok=clip.commercial_ok, source_record_key=record_key,
                    ),
                )
            return len(shots)

