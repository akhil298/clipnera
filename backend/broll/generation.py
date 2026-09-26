"""AI-generated B-roll with Veo (Pro only), for scenes the library cannot fill.

The shot is generated vertical, then goes through the same renditions as stock
footage and is stored as a private library asset of the user who paid for it:
it is never shown to anyone else. Credits are taken before the call and
returned if generation fails.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from broll import renditions
from broll.ingest import upload_renditions
from broll.model import AssetKind, AssetStatus, BrollAsset, BrollLicense
from broll.repository import BrollRepository
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from jobs.queue import Job, get_queue
from subscription.service import SubscriptionService
from usage.recorder import record_llm_call

log = get_logger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta"
GENERATE_JOB = "broll.generate"
POLL_SECONDS = 10.0
MAX_WAIT_SECONDS = 600.0
# A 429 is often a brief rate limit; a key without Veo quota keeps failing, and
# the job then refunds the credits.
START_ATTEMPTS = 3
RETRY_SECONDS = 20.0


def master_prompt(shot: str, context: str = "") -> str:
    """The Veo prompt for one B-roll shot: what to show, how it should look, what to avoid."""
    about = f" It illustrates: \"{context[:200]}\"." if context else ""
    return (
        f"Vertical 9:16 cinematic stock footage of {shot}.{about} Photorealistic, natural light, one continuous "
        "shot with a slow smooth camera move, shallow depth of field, rich but true colour. No text, no captions, "
        "no logos, no watermarks, no brand names, no recognisable real people."
    )


class VeoClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._key, self._model = api_key, model

    async def generate(self, prompt: str, seconds: int, resolution: str, out: Path) -> None:
        headers = {"x-goog-api-key": self._key}
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"aspectRatio": "9:16", "resolution": resolution, "durationSeconds": seconds},
        }
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            for attempt in range(1, START_ATTEMPTS + 1):
                started = await client.post(f"{API}/models/{self._model}:predictLongRunning", headers=headers, json=body)
                if started.status_code != 429 or attempt == START_ATTEMPTS:
                    break
                await asyncio.sleep(RETRY_SECONDS * attempt)
            started.raise_for_status()
            name = started.json()["name"]
            waited = 0.0
            while True:
                operation = (await client.get(f"{API}/{name}", headers=headers)).json()
                if operation.get("done"):
                    break
                if waited >= MAX_WAIT_SECONDS:
                    raise TimeoutError("Veo did not finish in time")
                await asyncio.sleep(POLL_SECONDS)
                waited += POLL_SECONDS
            if "error" in operation:
                raise RuntimeError(f"Veo refused the shot: {operation['error'].get('message', operation['error'])}")
            uri = operation["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
            video = await client.get(uri, headers=headers)
            video.raise_for_status()
            out.write_bytes(video.content)


async def create_generated_asset(user_id: str, prompt: str, title: str) -> str:
    """Generate, render and store a private shot; returns its asset id."""
    settings = get_settings()
    asset_id = str(uuid4())
    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        raw = work / "veo.mp4"
        started = time.monotonic()
        await VeoClient(settings.GEMINI_API_KEY, settings.VEO_MODEL).generate(prompt, settings.VEO_SECONDS, settings.VEO_RESOLUTION, raw)
        await record_llm_call("gemini", settings.VEO_MODEL, video_seconds=float(settings.VEO_SECONDS),
                              resolution=settings.VEO_RESOLUTION, latency_ms=int((time.monotonic() - started) * 1000))
        info = await renditions.probe(str(raw))
        vertical, proxy, thumb = await renditions.render_shot(str(raw), work, 0.0, info.duration)
        keys = await upload_renditions(S3(), asset_id, vertical, proxy, thumb)
    async with AsyncSessionLocal() as session:
        await BrollRepository(session).add(
            BrollAsset(
                id=asset_id, kind=AssetKind.GENERATED, source="veo", source_id=asset_id, title=title[:300],
                caption=prompt[:1000], tags=[], search_text=title, duration_s=round(info.duration, 3),
                width=info.width, height=info.height, orientation="portrait", fps=round(info.fps, 3),
                quality_score=0.9, status=AssetStatus.LIVE, owner_user_id=user_id, **keys,
            ),
            BrollLicense(license_code="ai_generated", author="Generated for this user with Veo", commercial_ok=True),
        )
    return asset_id


async def start_generation(session, user_id: str, shot: str, context: str, target: dict[str, Any]) -> None:
    """Check the plan, take the credits and queue a generation for ``target``."""
    settings = get_settings()
    subscriptions = SubscriptionService.for_session(session)
    if not (await subscriptions.get_entitlements(user_id)).pro_ai_provider:
        raise CustomException(message="AI-generated scenes are a Pro feature.", code="PRO_REQUIRED", status_code=403)
    if not settings.GEMINI_API_KEY:
        raise CustomException(message="AI generation is not configured", code="GENERATION_UNAVAILABLE", status_code=503)
    await subscriptions.consume_daily_quota(user_id, "ai_shots")
    try:
        await subscriptions.deduct_credits(
            user_id=user_id, amount=settings.VEO_SCENE_CREDITS, reason=f"AI-generated scene: {shot[:60]}",
            reference_id=target.get("id"), reference_type="ai_scene",
        )
    except Exception as exc:
        raise CustomException(message=str(exc), code="INSUFFICIENT_CREDITS", status_code=402)
    await get_queue().enqueue(Job(GENERATE_JOB, {
        "user_id": user_id, "prompt": master_prompt(shot, context), "title": shot,
        "credits": settings.VEO_SCENE_CREDITS, "target": target,
    }))
