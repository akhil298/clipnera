"""Runs a queued AI shot and puts it where it was asked for: a reel scene or a clip cutaway."""

from __future__ import annotations

from typing import Any

from broll.cutaways import dump_plan, load_plan
from broll.generation import GENERATE_JOB, create_generated_asset
from clip_generation.repository import ClipRepository
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from jobs.queue import Job, handler
from reels.model import ReelProject
from reels.planner import scenes_from_json, scenes_to_json
from subscription.service import SubscriptionService

log = get_logger(__name__)


@handler(GENERATE_JOB)
async def run_generation(job: Job) -> None:
    payload = job.payload
    user_id, target = payload["user_id"], payload["target"]
    asset_id = None
    try:
        asset_id = await create_generated_asset(user_id, payload["prompt"], payload["title"])
    except Exception as exc:
        log.warning("AI shot failed, refunding: target=%s error=%s", target, exc)
        async with AsyncSessionLocal() as session:
            await SubscriptionService.for_session(session).refund_credits(
                user_id=user_id, amount=payload["credits"], reason="AI-generated scene failed, refund",
                reference_id=target.get("id"), reference_type="ai_scene_refund",
            )
    await place(target, user_id, asset_id)


async def place(target: dict[str, Any], user_id: str, asset_id: str | None) -> None:
    """Clear the generating flag and, when a shot was made, swap it in (the old shot becomes an alternate)."""
    index = target["index"]
    async with AsyncSessionLocal() as session:
        if target["type"] == "reel_scene":
            reel = await session.get(ReelProject, target["id"])
            scenes = scenes_from_json(reel.scenes) if reel else []
            if 0 <= index < len(scenes):
                scene = scenes[index]
                scene.generating = False
                if asset_id:
                    scene.alternates = [a for a in [scene.asset_id, *scene.alternates] if a]
                    scene.kind, scene.asset_id = "broll", asset_id
                reel.scenes = scenes_to_json(scenes)
                await session.commit()
        elif target["type"] == "clip_placement":
            repo = ClipRepository(session)
            clip = await repo.get_clip(target["id"], user_id)
            plan = load_plan(clip.broll_plan) if clip else []
            if 0 <= index < len(plan):
                placement = plan[index]
                placement.generating = False
                if asset_id:
                    placement.alternates = [placement.asset_id, *placement.alternates]
                    placement.asset_id = asset_id
                await repo.update_clip(clip.id, user_id, broll_plan=dump_plan(plan))
