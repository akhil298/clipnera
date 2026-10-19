"""Planning motion graphics for a project's clips, and handing them to exports.

Planned once, after clip generation, and stored on each clip under
``analysis_json["motion"]``; every export draws from it (see
``subtitle_styling.service``). Planning never fails a pipeline run: a clip
without graphics is still a clip.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from broll.cutaways import clip_words
from clients.ai import get_text_client
from clip_generation.hook import parse_spans
from clip_generation.repository import ClipRepository
from content_intelligence.signals import extract_audio_signals
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from motion.moments import find_moments, loud_moments, reactions
from motion.overlay import MotionSource
from motion.plan import MotionPlan, dump_plan, load_plan
from motion.planner import plan_motion

log = get_logger(__name__)

PLAN_BATCH = 6


async def plan_project_motion(
    project_id: str, user_id: str, is_pro: bool, video_path: str | None = None,
    notify: Callable[[str, int], None] | None = None,
) -> int:
    """Plan and store graphics for every clip of a project; returns how many clips got any.

    Pro clips get the full set, the rest the light one (see ``motion.planner``).
    ``video_path`` (the local source) lets loud reactions be found; without it
    only spoken moments are planned.
    """
    async with AsyncSessionLocal() as session:
        clips = await ClipRepository(session).list_clips(project_id, user_id)
    if not clips:
        return 0
    loudness = await extract_audio_signals(video_path) if video_path else None
    client = get_text_client(is_pro=is_pro, step="motion_planning")
    planned: dict[str, MotionPlan] = {}
    for start in range(0, len(clips), PLAN_BATCH):
        batch = clips[start:start + PLAN_BATCH]
        if notify:
            notify(f"Planning graphics for clips {start + 1}-{start + len(batch)}...", int(100 * start / len(clips)))
        words = [clip_words(clip) for clip in batch]
        categories = [str(getattr(clip.content_category, "value", clip.content_category) or "") for clip in batch]
        loud = [loud_moments(loudness, clip_word.spans) for clip_word in words]
        try:
            found = await find_moments(words, client, categories, loud)
        except Exception as exc:
            log.warning("Motion planning failed for a batch, those clips keep no graphics: %s", exc)
            continue
        for clip, clip_moments, clip_word in zip(batch, found, words):
            clip_moments.moments += reactions(loudness, clip_word.words, clip_word.spans)
            clip_moments.moments.sort(key=lambda moment: moment.start)
            planned[clip.id] = _plan_for(clip, clip_moments, lite=not is_pro)

    with_graphics = 0
    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        for clip in clips:
            plan = planned.get(clip.id)
            if plan is None:
                continue
            analysis = _loads(clip.analysis_json)
            analysis["motion"] = dump_plan(plan)
            await repo.update_clip(clip.id, user_id, analysis_json=json.dumps(analysis))
            with_graphics += bool(plan.cues)
            log.info("Motion plan: clip=%s mood=%s cues=%s", clip.id, plan.mood,
                     ",".join(f"{c.kind}@{c.start:.1f}" for c in plan.cues) or "none")
    return with_graphics


def _plan_for(clip: Any, found: Any, lite: bool) -> MotionPlan:
    spans = parse_spans(clip.edit_spans) or [(clip.start_time, clip.end_time)]
    return plan_motion(found, spans[0][0], spans[-1][1], sum(end - start for start, end in spans), lite=lite)


def motion_source(clip: Any, ratio: str = "9:16") -> MotionSource | None:
    """The stored plan and the cut's layout stretches at ``ratio``, for an export.

    The stretches come even without a plan: the title card is placed from them.
    A clip with graphic beats draws those in its finish pass instead of these
    cues, and its captions step aside where a beat holds the frame.
    ``None`` when the clip has neither (cut before layouts were recorded).
    """
    from beats.compose import caption_quiet
    from clip_generation.hook import Hook

    analysis = _loads(clip.analysis_json)
    quiet = tuple(caption_quiet(clip, Hook.from_values(clip.hook_start, clip.hook_end))) if analysis.get("beats") else ()
    plan = None if analysis.get("beats") else load_plan(analysis.get("motion"))
    formats = _loads(clip.output_formats)
    frames = (formats.get(ratio) or {}).get("frames") if isinstance(formats.get(ratio), dict) else None
    if not frames and not quiet and (plan is None or not plan.cues):
        return None
    return MotionSource(plan, frames or [], quiet)


def _loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        loaded = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}
