from __future__ import annotations

from broll.ingest import Ingestor
from broll.model import AssetStatus, BrollAsset
from broll.repository import BrollRepository
from broll.cutaways import Placement, dump_plan, load_plan
from broll.generation import start_generation
from broll.model import BrollUsage
from broll.retrieval import BrollRetriever, SceneQuery
from broll.schema import (
    BrollAssetListResponse,
    BrollAssetResponse,
    BrollIngestRequest,
    BrollIngestResponse,
    BrollPlacementResponse,
    BrollPlacementUpdate,
    BrollPreview,
    BrollStatusRequest,
    ClipBrollResponse,
)
from clip_generation.repository import ClipRepository
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from jobs.queue import Job, get_queue, handler

INGEST_JOB = "broll.ingest"
PREVIEW_URL_TTL_SECONDS = 3600


class BrollService:
    def __init__(self, repo: BrollRepository, s3: S3 | None = None) -> None:
        self._repo = repo
        self._s3 = s3 or S3()
        self._bucket = get_settings().S3_BUCKET_NAME

    async def list_assets(self, query: str | None, status: str | None, limit: int, offset: int) -> BrollAssetListResponse:
        status_filter = AssetStatus(status) if status else None
        assets, total = await self._repo.list_assets(query, status_filter, limit, offset)
        return BrollAssetListResponse(items=[await self.to_response(a) for a in assets], total=total)

    async def set_status(self, asset_id: str, request: BrollStatusRequest) -> BrollAssetResponse:
        if not await self._repo.set_status(asset_id, AssetStatus(request.status), request.reason):
            raise CustomException(message="Asset not found", code="NOT_FOUND", status_code=404)
        return await self.to_response(await self._repo.get(asset_id))

    async def queue_ingest(self, request: BrollIngestRequest) -> BrollIngestResponse:
        await get_queue().enqueue(Job(INGEST_JOB, request.model_dump()))
        return BrollIngestResponse(query=request.query, queued=True)

    async def to_response(self, asset: BrollAsset) -> BrollAssetResponse:
        license_row = await self._repo.license_for(asset.id)
        return BrollAssetResponse(
            id=asset.id, kind=asset.kind.value, source=asset.source, source_id=asset.source_id,
            source_url=asset.source_url, title=asset.title, tags=list(asset.tags or []), duration_s=asset.duration_s,
            width=asset.width, height=asset.height, orientation=asset.orientation, quality_score=asset.quality_score,
            status=asset.status.value, status_reason=asset.status_reason,
            license_code=license_row.license_code if license_row else None,
            attribution_text=license_row.attribution_text if license_row else None,
            thumb_url=self.preview_url(asset.thumb_key), proxy_url=self.preview_url(asset.proxy_key),
            created_at=asset.created_at,
        )

    def preview_url(self, key: str | None) -> str | None:
        """Short-lived link to a low-resolution preview; masters are never linked."""
        return self._s3.generate_presigned_url(self._bucket, key, PREVIEW_URL_TTL_SECONDS) if key else None

    async def preview(self, asset: BrollAsset) -> BrollPreview:
        """What a user may see of a shot: preview, thumbnail and credit line."""
        license_row = await self._repo.license_for(asset.id)
        return BrollPreview(
            id=asset.id, title=asset.title, duration_s=asset.duration_s,
            thumb_url=self.preview_url(asset.thumb_key), proxy_url=self.preview_url(asset.proxy_key),
            attribution_text=license_row.attribution_text if license_row else None,
        )


class ClipBrollService:
    """A user's view of, and edits to, one clip's cutaways."""

    def __init__(self, session, s3: S3 | None = None) -> None:
        self._session = session
        self._clips = ClipRepository(session)
        self._repo = BrollRepository(session)
        self._assets = BrollService(self._repo, s3)

    async def get(self, clip_id: str, user_id: str) -> ClipBrollResponse:
        clip = await self._clip(clip_id, user_id)
        return await self._response(clip_id, load_plan(clip.broll_plan))

    async def update(self, clip_id: str, user_id: str, index: int, change: BrollPlacementUpdate) -> ClipBrollResponse:
        clip = await self._clip(clip_id, user_id)
        plan = load_plan(clip.broll_plan)
        if not 0 <= index < len(plan):
            raise CustomException(message="No such cutaway", code="NOT_FOUND", status_code=404)
        replaced = plan[index]
        if change.remove:
            plan.pop(index)
        elif change.asset_id:
            asset = await self._repo.get(change.asset_id)
            if asset is None or asset.status != AssetStatus.LIVE or asset.owner_user_id not in (None, user_id):
                raise CustomException(message="That shot is not available", code="NOT_FOUND", status_code=404)
            alternates = [a for a in [replaced.asset_id, *replaced.alternates] if a != asset.id]
            plan[index] = Placement(replaced.start, replaced.end, replaced.query, asset.id, replaced.score, alternates)
        else:
            raise CustomException(message="Give asset_id or remove", code="INVALID_BODY", status_code=400)
        # Swaps and removals are the library's quality signal.
        await self._repo.record_usage([BrollUsage(asset_id=replaced.asset_id, project_id=clip.project_id,
                                                  user_id=user_id, scene_index=index, swapped=True)])
        await self._clips.update_clip(clip_id, user_id, broll_plan=dump_plan(plan))
        return await self._response(clip_id, plan)

    async def generate(self, clip_id: str, user_id: str, index: int, shot: str | None) -> ClipBrollResponse:
        """Pro: replace one cutaway's shot with an AI-generated one."""
        clip = await self._clip(clip_id, user_id)
        plan = load_plan(clip.broll_plan)
        if not 0 <= index < len(plan):
            raise CustomException(message="No such cutaway", code="NOT_FOUND", status_code=404)
        if plan[index].generating:
            raise CustomException(message="This cutaway is already generating", code="ALREADY_GENERATING", status_code=409)
        plan[index].generating = True
        await self._clips.update_clip(clip_id, user_id, broll_plan=dump_plan(plan))
        try:
            await start_generation(self._session, user_id, shot or plan[index].query, plan[index].query,
                                   {"type": "clip_placement", "id": clip_id, "index": index})
        except Exception:
            plan[index].generating = False
            await self._clips.update_clip(clip_id, user_id, broll_plan=dump_plan(plan))
            raise
        return await self._response(clip_id, plan)

    async def search(self, query: str, min_duration: float = 0.0) -> list[BrollPreview]:
        """The shared library only: a hand search should not hide shots this user used lately."""
        picks = await BrollRetriever(self._repo).find([SceneQuery(query, min_duration)])
        return [await self._assets.preview(s.asset) for s in picks[0].ranked] if picks else []

    async def _clip(self, clip_id: str, user_id: str):
        clip = await self._clips.get_clip(clip_id, user_id)
        if not clip:
            raise CustomException(message="Clip not found", code="NOT_FOUND", status_code=404)
        return clip

    async def _response(self, clip_id: str, plan: list) -> ClipBrollResponse:
        ids = [a for p in plan for a in [p.asset_id, *p.alternates]]
        assets = {a.id: a for a in await self._repo.get_many(ids)}
        placements = []
        for index, p in enumerate(plan):
            asset = assets.get(p.asset_id)
            placements.append(BrollPlacementResponse(
                index=index, start=p.start, end=p.end, query=p.query, score=p.score, generating=p.generating,
                asset=await self._assets.preview(asset) if asset else None,
                alternates=[await self._assets.preview(assets[a]) for a in p.alternates if a in assets],
            ))
        return ClipBrollResponse(clip_id=clip_id, placements=placements)


@handler(INGEST_JOB)
async def _run_ingest(job: Job) -> None:
    request = BrollIngestRequest.model_validate(job.payload)
    async with AsyncSessionLocal() as session:
        await Ingestor(BrollRepository(session)).ingest_query(request.query, request.per_source, request.sources)

