"""The reel engine end to end: raw footage in, a premium reel and its Edit Plan out.

    ingest -> understand (listen + watch, in parallel) -> direct -> verify -> compile -> assets
           -> picture -> layout -> [graphics -> sound -> compose -> review -> revise]* -> deliver

Every stage writes into the Edit Plan and reports progress through ``on_progress``, so the reels UI can show
where the edit is. The review loop runs at most ``passes`` times and keeps the best-scoring version.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from core.logging_config import get_logger
from reel_engine import layout, sound
from reel_engine.assets import AssetStore, Scout
from reel_engine.compile import brief_of, captions_track, graphics_track, video_track
from reel_engine.director import direct, recipe
from reel_engine.listen import listen
from reel_engine.media import probe
from reel_engine.plan import EditPlan, Progress, Source
from reel_engine.render import compose, render_graphics, render_picture, resolve_behind
from reel_engine.review import apply, review
from reel_engine.verify import verify
from reel_engine.watch import watch

log = get_logger(__name__)

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
AUDIO_TYPES = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
IMAGE_SECONDS = 3.0
SHIP_SCORE = 8.0
STAGES = ("ingest", "listen", "watch", "direct", "verify", "compile", "assets", "picture", "layout", "graphics", "sound",
          "compose", "review", "done")
Progress_ = Callable[[EditPlan], Awaitable[None]] | None


def ingest(paths: list[Path]) -> list[Source]:
    sources = []
    for n, path in enumerate(paths):
        ext = path.suffix.lower()
        if ext in IMAGE_TYPES:
            from reel_engine.media import frame

            image = frame(path, 0.0, 1080)
            h, w = (image.shape[:2] if image is not None else (1920, 1080))
            sources.append(Source(index=n, name=path.name, path=str(path), kind="image", duration=IMAGE_SECONDS, width=w, height=h))
            continue
        info = probe(path)
        kind = "audio" if ext in AUDIO_TYPES or not info["has_video"] else "video"
        sources.append(Source(index=n, name=path.name, path=str(path), kind=kind, duration=round(info["duration"], 3),
                              width=info["width"], height=info["height"], fps=info["fps"], has_audio=info["has_audio"]))
    return sources


async def run(inputs: list[Path], work: Path, out: Path, store: AssetStore, owner: str = "", brief: str = "",
              target_seconds: float = 0.0, passes: int = 2, on_progress: Progress_ = None) -> EditPlan:
    work.mkdir(parents=True, exist_ok=True)
    plan = EditPlan()
    started = time.monotonic()

    async def stage(name: str, note: str = "") -> None:
        plan.progress.append(Progress(stage=name, note=note, at=round(time.monotonic() - started, 1)))
        log.info("Reel engine: %s %s", name, note)
        if on_progress:
            await on_progress(plan)

    await stage("ingest", f"{len(inputs)} file(s)")
    plan.sources = ingest(inputs)
    await stage("listen", "voice, music and words; shots and faces")
    audio, (shots, tracks, jpegs, how) = await asyncio.gather(listen(plan.sources, work), watch(plan.sources))
    plan.audio, plan.shots, plan.face_track = audio, shots, tracks
    await stage("watch", f"{audio.kind}: {audio.why}; {len(shots)} shots")

    await stage("direct", "planning the story")
    d = await direct(plan.sources, audio, shots, jpegs, how, brief, target_seconds)
    plan.ai_calls += 1
    words = audio.words
    for fix in d.spelling:
        if 0 <= fix.id < len(words) and fix.word.strip():
            words[fix.id].text = fix.word.strip()

    await stage("verify", "checking hooks and labels against the footage")
    hook, hook_why, changes = await verify(d, plan.sources, words)
    plan.ai_calls += 1
    plan.hooks = [f"{'*' if n == hook else ' '} {h.why}" for n, h in enumerate(d.hooks)]

    await stage("compile", "; ".join(changes[:4]) or "labels verified")
    plan.brief, _ = brief_of(d, audio, target_seconds)
    src_len = {s.index: s.duration for s in plan.sources}
    plan.video = video_track(d, plan.brief, words, shots, src_len, hook)
    if not plan.video:
        raise RuntimeError("the director's story had no usable clips")
    plan.duration = plan.video[-1].out1
    plan.graphics = graphics_track(d, plan.brief, words, plan.video, shots)
    plan.captions, plan.graphics = captions_track(d, plan.brief, words, plan.video, plan.graphics)

    await stage("assets", "searching the library, making what is missing")
    scout = Scout(store, owner, work)
    for g in plan.graphics:
        query = g.data.get("icon_query", "")
        if query:
            g.asset = await scout.icon(query)
    for c in plan.captions:
        if c.icon_query:
            c.icon = await scout.icon(c.icon_query)

    await stage("picture", f"{len(plan.video)} shots, {plan.duration:.1f} s")
    picture = await render_picture(plan, recipe(plan.brief.recipe).get("grade", "teal_orange"), work)
    await resolve_behind(plan, picture, work)
    await stage("layout", "placing every graphic off faces and the action")
    await asyncio.to_thread(layout.place, plan.graphics, plan.captions, str(picture))

    best: tuple[float, Path, EditPlan] | None = None
    for n in range(max(1, passes)):
        pass_dir = work / f"pass{n}"
        pass_dir.mkdir(exist_ok=True)
        await stage("graphics", f"pass {n + 1}: {len(plan.graphics)} graphics, {len(plan.captions)} captions")
        placed = await render_graphics(plan, pass_dir)
        await stage("sound", "voice, music and effects")
        plan.audio_items = []
        mix = await sound.mix(plan, scout, pass_dir)
        await stage("compose", "final encode")
        final = await compose(plan, picture, placed, mix, pass_dir, pass_dir / "reel.mp4")
        await stage("review", f"pass {n + 1}")
        try:
            result, actions = await review(plan, str(final))
        except Exception as exc:
            # A review that fails never fails the edit: ship the best pass so far, or this one unreviewed.
            log.warning("Review pass %d failed, shipping without it: %s", n + 1, exc)
            await stage("review", f"pass {n + 1}: review unavailable, keeping the best version")
            if best is None:
                best = (0.0, final, plan.model_copy(deep=True))
            break
        plan.ai_calls += 1
        result.passes = n + 1
        plan.review = result
        await stage("review", f"pass {n + 1} scored {result.overall}/10")
        if best is None or result.overall > best[0]:
            best = (result.overall, final, plan.model_copy(deep=True))
        if result.overall >= SHIP_SCORE or n + 1 >= passes:
            break
        if not apply(plan, actions):
            break
        await asyncio.to_thread(layout.place, plan.graphics, plan.captions, str(picture))

    _, final, plan_best = best
    plan = plan_best
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(final, out)
    plan.output = str(out)
    await scout.finish()
    plan.assets_made = [r.ref(made=True) for r in scout.made]
    await stage("done", f"review {plan.review.overall}/10 after {plan.review.passes} pass(es)")
    return plan
