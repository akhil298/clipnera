"""Planning graphic beats for a project's Pro clips, and reading them back for exports.

Planned once after clip generation and stored on each clip under
``analysis_json["beats"]``. A clip with beats is finished by
:func:`beats.compose.with_finish` (grade, zoom rhythm, graphics, sounds) before
its captions are burned; its old motion cues are not drawn, so a clip never
shows both engines. Planning never fails a run: a clip without beats keeps
the motion graphics it already has.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from beats.plan import BeatPlan, dump_plan, load_plan
from beats.planner import plan_beats
from broll.cutaways import clip_words
from clients.ai import get_text_client
from clip_generation.repository import ClipRepository
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from motion.service import _loads

log = get_logger(__name__)

PLAN_BATCH = 4


async def plan_project_beats(
    project_id: str, user_id: str, notify: Callable[[str, int], None] | None = None,
) -> int:
    """Plan and store beats for every clip of a Pro project; returns how many clips got any."""
    async with AsyncSessionLocal() as session:
        clips = await ClipRepository(session).list_clips(project_id, user_id)
    if not clips:
        return 0
    client = get_text_client(is_pro=True, step="beat_planning")
    planned: dict[str, BeatPlan] = {}
    for start in range(0, len(clips), PLAN_BATCH):
        batch = clips[start:start + PLAN_BATCH]
        if notify:
            notify(f"Designing graphics for clips {start + 1}-{start + len(batch)}...", int(100 * start / len(clips)))
        words = [clip_words(clip) for clip in batch]
        categories = [str(getattr(clip.content_category, "value", clip.content_category) or "") for clip in batch]
        try:
            plans = await plan_beats(words, client, categories)
        except Exception as exc:
            log.warning("Beat planning failed for a batch, those clips keep their motion graphics: %s", exc)
            continue
        planned.update({clip.id: plan for clip, plan in zip(batch, plans) if plan.beats})

    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        for clip in clips:
            plan = planned.get(clip.id)
            if plan is None:
                continue
            analysis = _loads(clip.analysis_json)
            analysis["beats"] = dump_plan(plan)
            await repo.update_clip(clip.id, user_id, analysis_json=json.dumps(analysis))
            log.info("Beat plan: clip=%s theme=%s beats=%s", clip.id, plan.theme,
                     ",".join(f"{b.kind}@{b.start:.1f}" for b in plan.beats))
    return len(planned)


def beat_plan(clip: Any) -> BeatPlan | None:
    """The clip's stored beats; ``None`` when it has none."""
    plan = load_plan(_loads(clip.analysis_json).get("beats"))
    return plan if plan and plan.beats else None

