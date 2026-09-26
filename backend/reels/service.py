"""Reels from images: create, upload, plan, edit the scene board, render."""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from broll.generation import start_generation
from broll.repository import BrollRepository
from broll.service import BrollService
from clients.services.s3 import S3
from core.config import get_settings
from core.exceptions import CustomException
from jobs.queue import Job, get_queue
from reels.model import ReelProject, ReelStatus
from reels.planner import scenes_from_json, scenes_to_json
from reels.schema import (
    ReelAssetsCompleteRequest,
    ReelAssetsInitRequest,
    ReelAssetsInitResponse,
    ReelAssetUpload,
    ReelCreateRequest,
    ReelResponse,
    ReelSceneResponse,
    ReelSceneUpdate,
    ReelSummary,
)
from subscription.service import SubscriptionService

PLAN_JOB = "reels.plan"
RENDER_JOB = "reels.render"
URL_TTL_SECONDS = 3600
_EXTENSIONS = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "audio/mpeg": ".mp3", "audio/wav": ".wav",
    "audio/x-wav": ".wav", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/webm": ".webm",
}


def render_credits(duration_s: float) -> int:
    """10 credits plus 1 per 2 seconds of output (see the pricing section of the plan)."""
    return get_settings().REEL_BASE_CREDITS + math.ceil(max(0.0, duration_s) / 2)


class ReelService:
    def __init__(self, session: AsyncSession, s3: S3 | None = None) -> None:
        self._session = session
        self._s3 = s3 or S3()
        self._settings = get_settings()
        self._broll = BrollRepository(session)
        self._previews = BrollService(self._broll, self._s3)

    async def create(self, user_id: str, request: ReelCreateRequest) -> ReelResponse:
        if not (request.topic or request.script):
            raise CustomException(message="Give a topic or a script", code="INVALID_BODY", status_code=400)
        reel = ReelProject(user_id=user_id, title=request.title, topic=request.topic, script=request.script,
                           language=request.language.lower(), style=request.style)
        self._session.add(reel)
        await self._session.commit()
        return await self.response(reel)

    async def list(self, user_id: str) -> list[ReelSummary]:
        rows = (await self._session.execute(
            select(ReelProject).where(ReelProject.user_id == user_id).order_by(ReelProject.created_at.desc()).limit(100)
        )).scalars().all()
        return [ReelSummary(id=r.id, title=r.title, status=r.status.value, duration_s=r.duration_s, created_at=r.created_at) for r in rows]

    async def get(self, user_id: str, reel_id: str) -> ReelResponse:
        return await self.response(await self._reel(user_id, reel_id))

    async def init_assets(self, user_id: str, reel_id: str, request: ReelAssetsInitRequest) -> ReelAssetsInitResponse:
        reel = await self._reel(user_id, reel_id, editable=True)
        images = [f for f in request.files if f.content_type.startswith("image/")]
        limit = await self._image_limit(user_id)
        if len(json.loads(reel.images)) + len(images) > limit:
            raise CustomException(message=f"Your plan allows up to {limit} images per reel.", code="IMAGE_LIMIT", status_code=403)
        if sum(1 for f in request.files if f.content_type.startswith("audio/")) > 1:
            raise CustomException(message="Upload one voiceover", code="INVALID_BODY", status_code=400)
        uploads = []
        for file in request.files:
            if file.content_type.startswith("image/") and file.size_bytes > 20 * 1024 * 1024:
                raise CustomException(message=f"{file.filename} is over 20 MB", code="UPLOAD_TOO_LARGE", status_code=413)
            key = f"reels/{user_id}/{reel.id}/{uuid4().hex}{_EXTENSIONS[file.content_type]}"
            url = self._s3.presign_put(self._settings.S3_BUCKET_NAME, key, file.content_type, URL_TTL_SECONDS)
            uploads.append(ReelAssetUpload(key=key, url=url, content_type=file.content_type))
        return ReelAssetsInitResponse(uploads=uploads)

    async def complete_assets(self, user_id: str, reel_id: str, request: ReelAssetsCompleteRequest) -> ReelResponse:
        reel = await self._reel(user_id, reel_id, editable=True)
        images = json.loads(reel.images)
        prefix = f"reels/{user_id}/{reel.id}/"
        for key in request.keys:
            if not key.startswith(prefix):
                raise CustomException(message="Unknown upload", code="INVALID_BODY", status_code=400)
            await asyncio.to_thread(self._s3.object_size, self._settings.S3_BUCKET_NAME, key)  # raises if missing
            if Path(key).suffix in (".jpg", ".png", ".webp"):
                if all(img["key"] != key for img in images):
                    images.append({"key": key, "description": "", "tags": [], "role": "other"})
            else:
                reel.voiceover_key = key
        reel.images = json.dumps(images)
        await self._session.commit()
        return await self.response(reel)

    async def plan(self, user_id: str, reel_id: str) -> ReelResponse:
        reel = await self._reel(user_id, reel_id, editable=True)
        reel.status, reel.error = ReelStatus.PLANNING, None
        await self._session.commit()
        await get_queue().enqueue(Job(PLAN_JOB, {"reel_id": reel.id, "user_id": user_id}))
        return await self.response(reel)

    async def update_scene(self, user_id: str, reel_id: str, index: int, change: ReelSceneUpdate) -> ReelResponse:
        reel = await self._reel(user_id, reel_id)
        if reel.status != ReelStatus.READY:
            raise CustomException(message="The scene board is not ready", code="REEL_NOT_READY", status_code=409)
        scenes = scenes_from_json(reel.scenes)
        if not 0 <= index < len(scenes):
            raise CustomException(message="No such scene", code="NOT_FOUND", status_code=404)
        scene = scenes[index]
        if change.kind == "image":
            if change.image_index is None or change.image_index >= len(json.loads(reel.images)):
                raise CustomException(message="No such image", code="INVALID_BODY", status_code=400)
            scene.image_index = change.image_index
        elif change.kind == "broll":
            asset = await self._broll.get(change.asset_id or "")
            if asset is None or asset.status.value != "live" or asset.owner_user_id not in (None, user_id):
                raise CustomException(message="That shot is not available", code="NOT_FOUND", status_code=404)
            if scene.asset_id and scene.asset_id != asset.id:
                scene.alternates = [a for a in [scene.asset_id, *scene.alternates] if a != asset.id]
            scene.asset_id = asset.id
        else:
            if not (change.headline or "").strip():
                raise CustomException(message="A text scene needs a headline", code="INVALID_BODY", status_code=400)
            scene.headline = change.headline.strip()
        scene.kind = change.kind
        reel.scenes = scenes_to_json(scenes)
        await self._session.commit()
        return await self.response(reel)

    async def generate_scene(self, user_id: str, reel_id: str, index: int, shot: str | None) -> ReelResponse:
        """Queue an AI shot for one scene (Pro); the board shows it generating until it lands."""
        reel = await self._reel(user_id, reel_id)
        if reel.status not in (ReelStatus.READY, ReelStatus.DONE):
            raise CustomException(message="The scene board is not ready", code="REEL_NOT_READY", status_code=409)
        scenes = scenes_from_json(reel.scenes)
        if not 0 <= index < len(scenes):
            raise CustomException(message="No such scene", code="NOT_FOUND", status_code=404)
        scene = scenes[index]
        if scene.generating:
            raise CustomException(message="This scene is already generating", code="ALREADY_GENERATING", status_code=409)
        description = shot or scene.query or scene.headline or " ".join(scene.text.split()[:12])
        await self._set_generating(reel, scenes, index, True)
        try:
            await start_generation(self._session, user_id, description, scene.text,
                                   {"type": "reel_scene", "id": reel.id, "index": index})
        except Exception:
            await self._set_generating(reel, scenes_from_json(reel.scenes), index, False)
            raise
        return await self.response(reel)

    async def _set_generating(self, reel: ReelProject, scenes: list, index: int, value: bool) -> None:
        scenes[index].generating = value
        reel.scenes = scenes_to_json(scenes)
        await self._session.commit()

    async def render(self, user_id: str, reel_id: str) -> ReelResponse:
        reel = await self._reel(user_id, reel_id)
        if reel.status not in (ReelStatus.READY, ReelStatus.DONE):
            raise CustomException(message="Plan the reel before rendering it", code="REEL_NOT_READY", status_code=409)
        if any(s.generating for s in scenes_from_json(reel.scenes)):
            raise CustomException(message="Wait for the AI shots to finish", code="REEL_BUSY", status_code=409)
        credits = render_credits(reel.duration_s)
        await SubscriptionService.for_session(self._session).consume_daily_quota(user_id, "reel_renders")
        try:
            await SubscriptionService.for_session(self._session).deduct_credits(
                user_id=user_id, amount=credits, reason=f"Reel render: {reel.duration_s:.0f}s",
                reference_id=reel.id, reference_type="reel_render",
            )
        except Exception as exc:
            raise CustomException(message=str(exc), code="INSUFFICIENT_CREDITS", status_code=402)
        reel.status, reel.error, reel.credits_charged = ReelStatus.RENDERING, None, credits
        await self._session.commit()
        await get_queue().enqueue(Job(RENDER_JOB, {"reel_id": reel.id, "user_id": user_id, "credits": credits}))
        return await self.response(reel)

    async def _image_limit(self, user_id: str) -> int:
        entitlements = await SubscriptionService.for_session(self._session).get_entitlements(user_id)
        return self._settings.REEL_MAX_IMAGES_PRO if entitlements.pro_ai_provider else self._settings.REEL_MAX_IMAGES_FREE

    async def _reel(self, user_id: str, reel_id: str, editable: bool = False) -> ReelProject:
        reel = await self._session.get(ReelProject, reel_id)
        if reel is None or reel.user_id != user_id:
            raise CustomException(message="Reel not found", code="NOT_FOUND", status_code=404)
        if editable and reel.status in (ReelStatus.PLANNING, ReelStatus.RENDERING):
            raise CustomException(message="The reel is busy; wait for it to finish", code="REEL_BUSY", status_code=409)
        return reel

    def _url(self, key: str | None) -> str | None:
        return self._s3.generate_presigned_url(self._settings.S3_BUCKET_NAME, key, URL_TTL_SECONDS) if key else None

    async def response(self, reel: ReelProject) -> ReelResponse:
        images = json.loads(reel.images)
        scenes = scenes_from_json(reel.scenes)
        asset_ids = [a for s in scenes for a in ([s.asset_id] if s.asset_id else []) + s.alternates]
        assets = {a.id: a for a in await self._broll.get_many(asset_ids)}

        async def preview(asset_id: str | None):
            asset = assets.get(asset_id) if asset_id else None
            return await self._previews.preview(asset) if asset else None

        scene_responses = []
        for index, scene in enumerate(scenes):
            image_url = self._url(images[scene.image_index]["key"]) if scene.kind == "image" and scene.image_index is not None and scene.image_index < len(images) else None
            scene_responses.append(ReelSceneResponse(
                index=index, start=scene.start, end=scene.end, text=scene.text, kind=scene.kind,
                image_index=scene.image_index, headline=scene.headline, query=scene.query, generating=scene.generating,
                image_url=image_url,
                footage=await preview(scene.asset_id) if scene.kind == "broll" else None,
                alternates=[p for p in [await preview(a) for a in scene.alternates] if p],
            ))
        return ReelResponse(
            id=reel.id, title=reel.title, status=reel.status.value, topic=reel.topic, script=reel.script,
            language=reel.language, style=reel.style, image_urls=[self._url(i["key"]) for i in images],
            has_voiceover=bool(reel.voiceover_key), duration_s=reel.duration_s, scenes=scene_responses,
            credits_estimate=render_credits(reel.duration_s) if scenes else 0, credits_charged=reel.credits_charged,
            output_url=self._url(reel.output_key), error=reel.error, created_at=reel.created_at,
        )
