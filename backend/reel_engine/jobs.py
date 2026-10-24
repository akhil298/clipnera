"""The premium footage reel's background job: the reel engine edits the uploaded footage end to end.

Credits are taken when the edit starts (``EditService.analyze``) and refunded if the job fails. Progress is
written to the edit's ``premium`` document after every stage, so the reels board can show where it is.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from edit_engine.model import EditProject, EditStatus
from edit_engine.pricing import reel_credits
from jobs.queue import Job, handler
from notifications.service import notify_reel_outcome
from reel_engine import pipeline, typekits
from reel_engine.media import cover
from reel_engine.moments import dump as moments_dump
from reel_engine.plan import EditPlan
from reel_engine.store import DbAssetStore
from subscription.service import InsufficientCreditsError, SubscriptionService
from usage.context import llm_scope

log = get_logger(__name__)

PREMIUM_JOB = "edits.premium"
DEFAULT_SECONDS = 45
REVIEW_PASSES = 2


def price(edit: EditProject) -> int:
    """Credits a premium edit costs: the classic reel's price at the AI director's rate, for the target length. It
    pays for reading the whole video (by its minutes) and the first reel."""
    raw = sum(float(s.get("duration") or 0) for s in json.loads(edit.sources) if s.get("kind") in ("video", "voice"))
    return reel_credits(edit.target_seconds or DEFAULT_SECONDS, raw, opus=True)


def extra_price(edit: EditProject) -> int:
    """Each further reel from the same video: the video is read once, so only the reel itself is paid for."""
    return reel_credits(edit.target_seconds or DEFAULT_SECONDS, 0.0, opus=True)


RECENT_EDITS = 3    # a creator's last edits whose type kits a new reel does not repeat


async def recent_kits(user_id: str, edit_id: str) -> frozenset[str]:
    """Type kits of the creator's last few premium edits, so their next reels look different."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(EditProject.premium).where(EditProject.user_id == user_id, EditProject.engine == "premium", EditProject.id != edit_id,
                                              EditProject.status == EditStatus.DONE)
            .order_by(EditProject.created_at.desc()).limit(RECENT_EDITS))).scalars().all()
    kits = set()
    for raw in rows:
        brief = (json.loads(raw or "{}").get("plan") or {}).get("brief") or {}
        if brief.get("type_kit"):
            kits.add(brief["type_kit"])
        if brief.get("kit"):
            kits.add(typekits.signature(brief["kit"]))
    return frozenset(kits)


THUMB_FRAMES = 10   # frames from the footage shown while it is read
THUMB_WIDTH = 320


def _thumbs(found: pipeline.Analysis, at: list[tuple[int, float]]) -> list[bytes]:
    """JPEG thumbnails of the sampled frame nearest each (source, second)."""
    from reel_engine.media import jpeg

    out = []
    for src, t in at:
        frames = found.frames.get(src) or []
        if frames:
            _, image = min(frames, key=lambda f: abs(f[0] - t))
            out.append(jpeg(image))
    return out


def summary(document: dict[str, Any]) -> dict[str, Any]:
    """The Edit Plan as the reels board shows it (``PremiumResponse`` fields)."""
    plan = EditPlan(**document["plan"]) if document.get("plan") else None
    stages = document.get("progress") or (plan.model_dump()["progress"] if plan else [])
    brief = plan.brief if plan else None
    return {
        "stage": stages[-1]["stage"] if stages else "queued",
        "stages": stages,
        "path": brief.path if brief else None, "recipe": brief.recipe if brief else None,
        "audio_kind": plan.audio.kind if plan else None, "audio_why": plan.audio.why if plan else None,
        "title": f"{brief.title_lead} {brief.title_text}".strip() if brief else None,
        "hooks": plan.hooks if plan else [], "sections": [f"{s.lead} {s.text}" for s in brief.sections] if brief else [],
        "shots": len(plan.video) if plan else 0, "graphics": len(plan.graphics) if plan else 0,
        "captions": len(plan.captions) if plan else 0,
        "scores": [s.model_dump() for s in plan.review.scores] if plan else [],
        "overall": plan.review.overall if plan else 0.0, "fixes": plan.review.fixes if plan else [],
        "passes": plan.review.passes if plan else 0,
        "assets": [{"kind": a.kind, "source": a.source, "made": a.made} for a in plan.assets_made] if plan else [],
        "ai_calls": plan.ai_calls if plan else 0,
        "music": f"{plan.music.title} · {plan.music.source.capitalize()}" if plan and plan.music else None,
        # S3 keys here; the edit service turns them into links.
        "frames": document.get("frames") or [],
        "planned": [{"title": r["title"], "seconds": int(r.get("seconds") or 0), "thumb_url": r.get("thumb"), "status": r["status"]}
                    for r in document.get("planned") or []],
    }


async def _save(edit_id: str, **fields: Any) -> None:
    async with AsyncSessionLocal() as session:
        edit = await session.get(EditProject, edit_id)
        for key, value in fields.items():
            setattr(edit, key, value)
        await session.commit()


def most_reels(is_pro: bool) -> int:
    settings = get_settings()
    return settings.REEL_MAX_REELS_PRO if is_pro else settings.REEL_MAX_REELS_FREE


# Premium edits this worker runs at once: they use every core, so two at once only make both slow.
_EDIT_SLOTS = asyncio.Semaphore(1)


@handler(PREMIUM_JOB)
async def premium_edit(job: Job) -> None:
    edit_id, user_id, credits = job.payload["edit_id"], job.payload["user_id"], job.payload["credits"]
    # first = the reading of the video and the first reel (charged when the edit started); per_reel = each further reel.
    charged = {"total": credits, "first": credits, "per_reel": credits}
    try:
        async with _EDIT_SLOTS:
            with llm_scope(user_id=user_id, step="reel_engine"):
                await _run(edit_id, user_id, charged)
    except Exception as exc:
        log.exception("Premium edit failed: edit=%s", edit_id)
        async with AsyncSessionLocal() as session:
            edit = await session.get(EditProject, edit_id)
            made = json.loads(edit.reels or "[]")
            # Reels already made are kept; everything paid for and not delivered (reels made side by side may be
            # several) goes back.
            refund = max(0, charged["total"] - (charged["first"] + charged["per_reel"] * (len(made) - 1) if made else 0))
            if made:
                edit.status, edit.error = EditStatus.DONE, None
            else:
                edit.status = EditStatus.FAILED
                edit.error = "The edit failed and your credits were refunded. Please try again."
            edit.credits_charged = max(0, edit.credits_charged - refund)
            await session.commit()
            if refund:
                await SubscriptionService.for_session(session).refund_credits(
                    user_id=user_id, amount=refund, reason=f"Premium reel failed, refund for {edit_id}",
                    reference_id=edit_id, reference_type="edit_render_refund",
                )
        await notify_reel_outcome(user_id, "your reel", success=bool(made))
        log.warning("Premium edit refunded %d credits: edit=%s (%s)", refund, edit_id, exc)


async def _run(edit_id: str, user_id: str, charged: dict[str, int]) -> None:
    settings = get_settings()
    s3 = S3()
    async with AsyncSessionLocal() as session:
        edit = await session.get(EditProject, edit_id)
        sources = [s for s in json.loads(edit.sources) if s.get("uploaded") and s["kind"] in ("video", "image", "voice")]
        brief = " ".join(filter(None, [edit.intent, edit.script]))
        target = float(edit.target_seconds or 0)
        title = edit.title
        is_pro = (await SubscriptionService.for_session(session).get_entitlements(user_id)).pro_ai_provider
        charged["per_reel"] = extra_price(edit)
        # A job resumed after a restart keeps what the last attempt did: its moments, reels and charges.
        made: list[dict[str, Any]] = json.loads(edit.reels or "[]")
        doc: dict[str, Any] = {k: v for k, v in json.loads(edit.premium or "{}").items() if k in ("frames", "moments", "planned")}
        charged["total"] = max(charged["first"], edit.credits_charged)
    paid = 1 + max(0, charged["total"] - charged["first"]) // max(1, charged["per_reel"])
    prefix = f"edits/{user_id}/{edit_id}"

    async def save_doc(**fields: Any) -> None:
        await _save(edit_id, premium=json.dumps(doc, ensure_ascii=False), **fields)

    async def report(plan: EditPlan) -> None:
        doc["progress"] = [p.model_dump() for p in plan.progress]
        await save_doc()

    async def upload_jpeg(key: str, data: bytes) -> str:
        await asyncio.to_thread(s3.put_object, settings.S3_BUCKET_NAME, key, data, ContentType="image/jpeg")
        return key

    async def analysed(found: pipeline.Analysis) -> None:
        """Frames from across the footage, shown while the edit is planned."""
        if doc.get("frames"):
            return
        videos = [s for s in found.sources if s.kind in ("video", "image")]
        at = [(s.index, s.duration * (k + 0.5) / THUMB_FRAMES) for s in videos for k in range(max(1, THUMB_FRAMES // max(1, len(videos))))]
        images = await asyncio.to_thread(_thumbs, found, at)
        doc["frames"] = [await upload_jpeg(f"{prefix}/thumbs/f{k}.jpg", data) for k, data in enumerate(images)]
        await save_doc()

    async def planned(found: pipeline.Analysis, windows: list) -> None:
        """The reels that will be made, each with a thumbnail from its moment, its hook and its status."""
        if doc.get("planned"):
            return
        if windows[0] is not None:
            doc["moments"] = moments_dump(windows)
        at = [(w[3], (w[1] + w[2]) / 2) if w else (found.sources[0].index, found.sources[0].duration / 2) for w in windows]
        images = await asyncio.to_thread(_thumbs, found, at)
        doc["planned"] = [{"title": (w[0].headline or w[0].title) if w else title, "seconds": round(w[2] - w[1]) if w else 0,
                           "thumb": await upload_jpeg(f"{prefix}/thumbs/m{n}.jpg", images[n]) if n < len(images) else None,
                           "status": "ready" if any(r["key"].endswith(f"/reel{n + 1}.mp4") for r in made) else "queued"}
                          for n, w in enumerate(windows)]
        await save_doc()

    async def status(n: int, state: str) -> None:
        if n < len(doc.get("planned") or []):
            doc["planned"][n]["status"] = state
            await save_doc()

    async def allow(n: int) -> bool:
        """Each reel after the first is charged before it is made (once, even across a restart); out of credits, the
        edit stops at the reels it has."""
        nonlocal paid
        if n < paid:
            return True
        async with AsyncSessionLocal() as session:
            try:
                await SubscriptionService.for_session(session).deduct_credits(
                    user_id=user_id, amount=charged["per_reel"], reason=f"Premium reel {n + 1}: {title}"[:200],
                    reference_id=edit_id, reference_type="edit_render")
            except InsufficientCreditsError:
                log.info("Premium edit %s stops at %d reels: out of credits", edit_id, n)
                return False
            edit = await session.get(EditProject, edit_id)
            edit.credits_charged += charged["per_reel"]
            await session.commit()
        charged["total"] += charged["per_reel"]
        paid += 1
        return True

    async def keep(n: int, plan: EditPlan, path: Path) -> None:
        key = f"{prefix}/reel{n + 1}.mp4"
        await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, key, str(path), "video/mp4")
        named = f"{plan.brief.title_lead} {plan.brief.title_text}".strip() if plan.brief else ""
        # A cover for the reels board and the player's poster: the reel's own frame with its hook headline up.
        image = await asyncio.to_thread(cover, path)
        thumb = await upload_jpeg(f"{prefix}/reel{n + 1}.jpg", image) if image else None
        made.append({"key": key, "duration": round(plan.duration, 2), "title": (named or title)[:300], "thumb": thumb})
        # Reels finish out of order when made side by side; they are listed in the order of their moments.
        made.sort(key=lambda r: int(r["key"].rsplit("reel", 1)[1].split(".")[0]))
        await _save(edit_id, reels=json.dumps(made, ensure_ascii=False))

    async def lost(n: int, exc: Exception) -> None:
        """One reel of several failed: the others carry on and this reel's charge goes back."""
        refund = charged["first"] if n == 0 else charged["per_reel"]
        async with AsyncSessionLocal() as session:
            edit = await session.get(EditProject, edit_id)
            edit.credits_charged = max(0, edit.credits_charged - refund)
            await session.commit()
            await SubscriptionService.for_session(session).refund_credits(
                user_id=user_id, amount=refund, reason=f"Premium reel {n + 1} failed, refund for {edit_id}",
                reference_id=edit_id, reference_type="edit_render_refund")
        charged["total"] -= refund
        log.warning("Premium edit %s: reel %d failed and was refunded (%s)", edit_id, n + 1, exc)

    done = frozenset(int(r["key"].rsplit("reel", 1)[1].split(".")[0]) - 1 for r in made)
    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        paths = []
        for n, source in enumerate(sources):
            local = work / f"src{n}{Path(source['key']).suffix}"
            await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, source["key"], str(local))
            paths.append(local)
        plans = await pipeline.run_many(paths, work / "engine", work / "reels", DbAssetStore(s3), owner=user_id, brief=brief,
                                        target_seconds=target, passes=REVIEW_PASSES, on_progress=report, most=most_reels(is_pro),
                                        allow=allow, on_reel=lambda n, plan: keep(n, plan, Path(plan.output)), on_fail=lost,
                                        parallel=settings.REEL_PARALLEL, known=doc.get("moments"), skip=done,
                                        on_analysed=analysed, on_moments=planned, on_status=status,
                                        avoid_kits=await recent_kits(user_id, edit_id))
    if not made:
        raise RuntimeError("no reel was made")
    first = plans[0] if plans else None
    named = first and first.brief and first.brief.title_text and title in ("", "Untitled reel")
    if first:
        doc["plan"] = first.model_dump()
        doc["progress"] = [p.model_dump() for p in first.progress]
    await save_doc(status=EditStatus.DONE, output_key=made[0]["key"], duration_s=made[0]["duration"], renders=len(made), error=None,
                   raw_seconds=round(sum(float(s.get("duration") or 0) for s in sources if s["kind"] == "video"), 3),
                   title=f"{first.brief.title_lead} {first.brief.title_text}".strip()[:300] if named else title)
    await notify_reel_outcome(user_id, title, success=True)
    log.info("Premium edit done: edit=%s %d reel(s)", edit_id, len(made))
