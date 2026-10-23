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
from reel_engine import icons, inserts, tracks
from reel_engine.compile import BEAT, brief_of, captions_track, graphics_track, to_output, video_track
from reel_engine.director import direct, recipe
from reel_engine.listen import listen
from reel_engine.media import probe
from reel_engine.plan import EditPlan, MusicChoice, Progress, Source
from reel_engine.render import compose, render_graphics, render_inserts, render_picture, resolve_behind
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


def add_photo_cards(plan: EditPlan) -> None:
    """Photo inserts styled as cards become graphics; a story graphic under one gives way to it."""
    from reel_engine.plan import GraphicItem

    cards = [i for i in plan.inserts if i.style == "card"]
    for card in cards:
        plan.graphics = [g for g in plan.graphics if not (g.kind in ("two", "tag", "keyword", "name", "count_up")
                                                          and g.start < card.end and card.start < g.end)]
        plan.graphics.append(GraphicItem(id=f"p{card.id}", kind="photocard", start=card.start, end=card.end, asset=card.asset,
                                         data={"text": card.label}, place="panel", why="photo of what is said", by="inserts"))
    plan.inserts = [i for i in plan.inserts if i.style != "card"]
    plan.graphics.sort(key=lambda g: g.start)
    plan.captions = [c for c in plan.captions if not any(c.start < k.end and k.start < c.end for k in cards)]


def reveal_at(plan: EditPlan, d, words) -> float | None:
    """Where the music should drop: the reveal word when someone talks, else the first step (or the payoff)."""
    if 0 <= d.drop_word < len(words):
        w = words[d.drop_word]
        return to_output(plan.video, w.src, w.t0)
    first_step = next((i.out0 for i in plan.video if i.section >= 0), None)
    return first_step if first_step is not None else next((i.out0 for i in plan.video if i.role == "payoff"), None)


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
    audio, (shots, face_track, jpegs, how) = await asyncio.gather(listen(plan.sources, work), watch(plan.sources))
    plan.audio, plan.shots, plan.face_track = audio, shots, face_track
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
    picture = plan.brief.path == "visual"
    track = tracks.pick(plan.brief.mood, target_seconds or plan.brief.target_seconds or 40, picture) if picture else None
    plan.video = video_track(d, plan.brief, words, shots, src_len, hook, beat=track.beat if track else BEAT)
    if not plan.video:
        raise RuntimeError("the director's story had no usable clips")
    plan.duration = plan.video[-1].out1
    track = track or tracks.pick(plan.brief.mood, plan.duration, picture)
    if track:
        plan.music = MusicChoice(key=track.key, path=str(track.path), title=track.title, mood=track.mood, bpm=track.bpm,
                                 offset=tracks.offset(track, reveal_at(plan, d, words), plan.duration),
                                 licence=track.licence, source=track.source)
    plan.graphics = graphics_track(d, plan.brief, words, plan.video, shots)
    plan.captions, plan.graphics = captions_track(d, plan.brief, words, plan.video, plan.graphics)

    await stage("assets", "searching the library, making what is missing")
    scout = Scout(store, owner, work)
    wanting = [g for g in plan.graphics if g.data.get("icon_query")] + [c for c in plan.captions if c.icon_query]
    picked = await icons.choose([(item.data["icon_query"], " ".join(str(item.data.get(k, "")) for k in ("lead", "text", "label")) + " " + item.why)
                                 if hasattr(item, "data") else (item.icon_query, " ".join(w["text"] for w in item.words))
                                 for item in wanting])
    plan.ai_calls += 1 if wanting else 0
    for item, asset in zip(wanting, picked):
        if hasattr(item, "data"):
            item.asset = asset
        else:
            item.icon = asset

    if d.inserts and plan.brief.path == "voice":
        await stage("assets", f"finding {len(d.inserts)} cutaways and photos")
        plan.inserts, calls = await inserts.resolve(d.inserts, plan.video, words, scout, work,
                                                    {s.index: s.path for s in plan.sources if s.kind == "video"},
                                                    {s.index: sum(1 for sh in plan.shots if sh.src == s.index) for s in plan.sources})
        plan.ai_calls += calls
        add_photo_cards(plan)
    grade = recipe(plan.brief.recipe).get("grade", "teal_orange")
    await stage("picture", f"{len(plan.video)} shots, {len(plan.inserts)} cutaways, {plan.duration:.1f} s")
    picture = await render_picture(plan, grade, work)
    picture = await render_inserts(plan, picture, grade, work)
    await resolve_behind(plan, picture, work)
    await stage("layout", "placing every graphic off faces and the action")
    await asyncio.to_thread(layout.place, plan.graphics, plan.captions, str(picture))

    best: tuple[float, Path, EditPlan] | None = None
    for n in range(max(1, passes)):
        pass_dir = work / f"pass{n}"
        pass_dir.mkdir(exist_ok=True)
        await stage("graphics", f"pass {n + 1}: {len(plan.graphics)} graphics, {len(plan.captions)} captions")
        try:
            placed = await render_graphics(plan, pass_dir)
        except Exception as exc:  # graphics that will not render never fail the edit
            log.warning("Graphics pass failed, continuing without them: %s", exc)
            await stage("graphics", "graphics unavailable for this pass")
            placed = []
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
