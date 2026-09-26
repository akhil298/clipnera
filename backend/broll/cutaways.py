"""B-roll cutaways for generated clips: plan once, apply at every export.

After clip generation, each clip gets a plan of cutaways (source-video seconds
plus the chosen library shot and alternates), stored on the clip. Exports
overlay those shots on the cut clip before captions are burned, so captions,
hooks and transitions sit on top unchanged. Users can swap or remove any
cutaway; the next export uses the edited plan.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from broll.embeddings import get_embedder
from broll.model import BrollUsage
from broll.planner import ClipWords, plan_cutaways
from broll.renditions import fill_filter, probe, run
from broll.repository import BrollRepository
from broll.retrieval import BrollRetriever, SceneQuery, Scored, coverage, terms
from clients.ai import get_text_client
from clients.services.s3 import S3
from clip_generation.hook import Hook, parse_spans, source_to_cut
from clip_generation.repository import ClipRepository
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from subscription.service import SubscriptionService

log = get_logger(__name__)

# A shot must cover at least this share of the scene's words to be used; a
# weaker match looks random on screen, and no cutaway beats a wrong one.
MIN_COVERAGE = 0.5
PLAN_BATCH = 6
FADE_SECONDS = 0.12


@dataclass
class Placement:
    start: float
    end: float
    query: str
    asset_id: str
    score: float
    alternates: list[str] = field(default_factory=list)
    generating: bool = False


def load_plan(value: str | None) -> list[Placement]:
    try:
        return [Placement(**item) for item in json.loads(value or "[]")]
    except (ValueError, TypeError):
        return []


def dump_plan(placements: list[Placement]) -> str:
    return json.dumps([asdict(p) for p in placements])


def clip_words(clip: Any) -> ClipWords:
    spans = parse_spans(clip.edit_spans) or [(clip.start_time, clip.end_time)]
    segments = json.loads(clip.transcript or "[]") if isinstance(clip.transcript, str) else (clip.transcript or [])
    words = [
        w for segment in segments for w in (segment.get("words") or [])
        if any(a <= float(w.get("start", -1)) < b for a, b in spans)
    ]
    return ClipWords(words=sorted(words, key=lambda w: float(w["start"])), spans=spans)


async def plan_project_broll(
    project_id: str, user_id: str, is_pro: bool, notify: Callable[[str, int], None] | None = None,
) -> int:
    """Plan and store cutaways for every clip of a project; returns how many clips got B-roll."""
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        clips = await ClipRepository(session).list_clips(project_id, user_id)
    if not clips:
        return 0
    client = get_text_client(is_pro=is_pro, step="broll_planning")
    planned: list[tuple[Any, list]] = []
    for start in range(0, len(clips), PLAN_BATCH):
        batch = clips[start:start + PLAN_BATCH]
        if notify:
            notify(f"Planning B-roll for clips {start + 1}-{start + len(batch)}...", int(100 * start / len(clips)))
        try:
            cutaways = await plan_cutaways([clip_words(c) for c in batch], client)
        except Exception as exc:
            log.warning("B-roll planning failed for a batch, those clips keep no B-roll: %s", exc)
            continue
        planned.extend(zip(batch, cutaways))

    with_broll = 0
    async with AsyncSessionLocal() as session:
        repo = BrollRepository(session)
        retriever = BrollRetriever(repo, get_embedder())
        subscriptions = SubscriptionService.for_session(session)
        clip_repo = ClipRepository(session)
        for clip, cutaways in planned:
            if not cutaways:
                continue
            picks = await retriever.find(
                [SceneQuery(f"{c.query} {c.subject}".strip(), c.end - c.start) for c in cutaways], user_id=user_id,
            )
            placements = [
                Placement(c.start, c.end, c.query, p.best.asset.id, p.best.score, [s.asset.id for s in p.ranked[1:]])
                for c, p in zip(cutaways, picks)
                if p.best and good_match(p.best, c.subject)
            ]
            log.info("B-roll for clip %s: %d planned, %d matched in the library", clip.id, len(cutaways), len(placements))
            if not placements:
                continue
            try:
                await subscriptions.deduct_credits(
                    user_id=user_id, amount=settings.BROLL_CREDITS_PER_CLIP,
                    reason=f"B-roll cutaways for clip {clip.id}", reference_id=clip.id, reference_type="broll_clip",
                )
            except Exception as exc:
                log.info("Stopping B-roll for project %s: %s", project_id, exc)
                break
            await clip_repo.update_clip(clip.id, user_id, broll_plan=dump_plan(placements))
            await repo.record_usage([
                BrollUsage(asset_id=p.asset_id, project_id=project_id, user_id=user_id, scene_index=i)
                for i, p in enumerate(placements)
            ])
            with_broll += 1
    log.info("B-roll planned: project=%s clips=%d/%d", project_id, with_broll, len(clips))
    return with_broll


def good_match(pick: Scored, subject: str) -> bool:
    """Shows everything the subject names, or most of the whole query; a wrong shot is worse than none."""
    subject_terms = terms(subject)
    if subject_terms and coverage(subject_terms, pick.asset.search_text) == 1.0:
        return True
    return pick.coverage >= MIN_COVERAGE


def overlay_graph(placements: list[tuple[float, float]], width: int, height: int) -> tuple[str, str]:
    """(graph, output label) laying input i+1 over input 0 during placement i, with short fades."""
    chains: list[str] = []
    current = "0:v"
    for index, (start, end) in enumerate(placements, start=1):
        duration = end - start
        chains.append(
            f"[{index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS+{start:.3f}/TB,"
            f"{fill_filter(width, height)},format=yuva420p,"
            f"fade=t=in:st={start:.3f}:d={FADE_SECONDS}:alpha=1,"
            f"fade=t=out:st={end - FADE_SECONDS:.3f}:d={FADE_SECONDS}:alpha=1[b{index}]"
        )
        chains.append(
            f"[{current}][b{index}]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})':eof_action=pass[v{index}]"
        )
        current = f"v{index}"
    return ";".join(chains), current


@asynccontextmanager
async def with_broll(video_path: str, clip: Any, hook: Hook | None) -> AsyncIterator[str]:
    """The cut to render from: with cutaways when the clip has a plan, else ``video_path``.

    A failure here never fails an export; the clip renders without B-roll.
    """
    if not load_plan(getattr(clip, "broll_plan", None)):
        yield video_path
        return
    with tempfile.TemporaryDirectory() as workdir:
        try:
            path = await apply_broll(video_path, clip, hook, Path(workdir))
        except Exception as exc:
            log.warning("B-roll overlay failed for clip %s, exporting without it: %s", clip.id, exc)
            path = video_path
        yield path


async def apply_broll(video_path: str, clip: Any, hook: Hook | None, workdir: Path, s3: S3 | None = None) -> str:
    """The cut clip with its planned cutaways laid over it; the input itself when it has none."""
    plan = load_plan(getattr(clip, "broll_plan", None))
    if not plan:
        return video_path
    spans = parse_spans(clip.edit_spans)
    timed: list[tuple[float, float, str]] = []
    for placement in plan:
        start = source_to_cut(placement.start, clip.start_time, clip.end_time, hook, spans)
        end = source_to_cut(placement.end, clip.start_time, clip.end_time, hook, spans)
        if start is not None and end is not None and end - start > 2 * FADE_SECONDS:
            timed.append((start, end, placement.asset_id))
    if not timed:
        return video_path

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        assets = {a.id: a for a in await BrollRepository(session).get_many([asset_id for *_, asset_id in timed])}
    s3 = s3 or S3()
    inputs: list[str] = []
    kept: list[tuple[float, float]] = []
    for index, (start, end, asset_id) in enumerate(timed):
        asset = assets.get(asset_id)
        if asset is None or not asset.vertical_key or asset.status.value != "live":
            continue
        local = workdir / f"broll{index}.mp4"
        await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, asset.vertical_key, str(local))
        inputs.append(str(local))
        kept.append((start, end))
    if not kept:
        return video_path

    info = await probe(video_path)
    graph, label = overlay_graph(kept, info.width, info.height)
    output = workdir / "with_broll.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", video_path]
    for path in inputs:
        cmd += ["-i", path]
    cmd += [
        "-filter_complex", graph, "-map", f"[{label}]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", str(output),
    ]
    await run(cmd)
    log.info("B-roll applied: clip=%s cutaways=%d", clip.id, len(kept))
    return str(output)

