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
from reel_engine import pipeline
from reel_engine.plan import EditPlan
from reel_engine.store import DbAssetStore
from subscription.service import InsufficientCreditsError, SubscriptionService
from usage.context import llm_scope

log = get_logger(__name__)

PREMIUM_JOB = "edits.premium"
DEFAULT_SECONDS = 45
REVIEW_PASSES = 2


def price(edit: EditProject) -> int:
    """Credits a premium edit costs: the classic reel's price at the AI director's rate, for the target length."""
    raw = sum(float(s.get("duration") or 0) for s in json.loads(edit.sources) if s.get("kind") in ("video", "voice"))
    return reel_credits(edit.target_seconds or DEFAULT_SECONDS, raw, opus=True)


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


@handler(PREMIUM_JOB)
async def premium_edit(job: Job) -> None:
    edit_id, user_id, credits = job.payload["edit_id"], job.payload["user_id"], job.payload["credits"]
    charged = {"total": credits, "per_reel": credits}
    try:
        with llm_scope(user_id=user_id, step="reel_engine"):
            await _run(edit_id, user_id, charged)
    except Exception as exc:
        log.exception("Premium edit failed: edit=%s", edit_id)
        async with AsyncSessionLocal() as session:
            edit = await session.get(EditProject, edit_id)
            made = json.loads(edit.reels or "[]")
            # Reels already made are kept; only what was paid for and not delivered goes back.
            refund = charged["per_reel"] if made else charged["total"]
            if made:
                edit.status, edit.error = EditStatus.DONE, None
            else:
                edit.status = EditStatus.FAILED
                edit.error = "The edit failed and your credits were refunded. Please try again."
            edit.credits_charged = max(0, edit.credits_charged - refund)
            await session.commit()
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
    made: list[dict[str, Any]] = []

    async def report(plan: EditPlan) -> None:
        await _save(edit_id, premium=json.dumps({"progress": [p.model_dump() for p in plan.progress]}))

    async def allow(n: int) -> bool:
        """Each reel after the first is charged before it is made; out of credits, the edit stops at the reels it has."""
        if n == 0:
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
        return True

    async def keep(n: int, plan: EditPlan, path: Path) -> None:
        key = f"edits/{user_id}/{edit_id}/reel{n + 1}.mp4"
        await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, key, str(path), "video/mp4")
        named = f"{plan.brief.title_lead} {plan.brief.title_text}".strip() if plan.brief else ""
        made.append({"key": key, "duration": round(plan.duration, 2), "title": (named or title)[:300]})
        await _save(edit_id, reels=json.dumps(made, ensure_ascii=False))

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        paths = []
        for n, source in enumerate(sources):
            local = work / f"src{n}{Path(source['key']).suffix}"
            await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, source["key"], str(local))
            paths.append(local)
        plans = await pipeline.run_many(paths, work / "engine", work / "reels", DbAssetStore(s3), owner=user_id, brief=brief,
                                        target_seconds=target, passes=REVIEW_PASSES, on_progress=report, most=most_reels(is_pro),
                                        allow=allow, on_reel=lambda n, plan: keep(n, plan, Path(plan.output)))
    plan = plans[0]
    named = plan.brief and plan.brief.title_text and title in ("", "Untitled reel")
    await _save(edit_id, status=EditStatus.DONE, output_key=made[0]["key"], duration_s=plan.duration, renders=len(made), error=None,
                raw_seconds=round(sum(s.duration for s in plan.sources if s.kind == "video"), 3),
                title=f"{plan.brief.title_lead} {plan.brief.title_text}".strip()[:300] if named else title,
                premium=json.dumps({"plan": plan.model_dump(), "progress": [p.model_dump() for p in plan.progress]}, ensure_ascii=False))
    await notify_reel_outcome(user_id, title, success=True)
    log.info("Premium edit done: edit=%s %d reel(s), first %.1fs review %.1f", edit_id, len(made), plan.duration, plan.review.overall)
