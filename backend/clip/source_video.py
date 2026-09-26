"""Where a project's source video lives on this machine.

The pipeline reads the source from local disk. YouTube downloads land here
directly; uploaded videos (and any source whose local copy is gone, e.g. on a
fresh worker) are fetched from S3 into the same folder on first use.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from clients.services.s3 import S3
from clip.model import VideoProject
from core.logging_config import get_logger

log = get_logger(__name__)

DOWNLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "download_videos"


def local_source_path(project: VideoProject) -> Path:
    suffix = Path(project.s3_key or "").suffix or ".mp4"
    return DOWNLOAD_DIR / f"{project.id}{suffix}"


async def ensure_local_copy(project: VideoProject, s3: S3 | None = None) -> str | None:
    """A readable local path to the source, downloading it from S3 if needed.

    None when the project has neither a local file nor an S3 object.
    """
    if project.local_path and Path(project.local_path).is_file():
        return project.local_path
    if not (project.s3_bucket and project.s3_key):
        return None
    target = local_source_path(project)
    if not target.is_file():
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".part")
        log.info("Fetching source video from S3: project=%s key=%s", project.id, project.s3_key)
        await asyncio.to_thread((s3 or S3()).download_file, project.s3_bucket, project.s3_key, str(partial))
        # Renamed only once complete, so a crash never leaves a truncated
        # file that a later run would mistake for the source.
        partial.replace(target)
    return str(target)
