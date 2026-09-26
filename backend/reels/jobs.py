"""The reel's two background jobs: plan the scene board, and render the reel."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from broll.cutaways import good_match
from broll.embeddings import get_embedder
from broll.renditions import probe
from broll.repository import BrollRepository
from broll.retrieval import BrollRetriever, SceneQuery
from clients.ai import get_text_client
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from jobs.queue import Job, handler
from reels import render as reel_render
from reels.model import ReelProject, ReelStatus
from reels.planner import (
    Scene, assign_visuals, avoid_repeats, fallback_image, scenes_from_json, scenes_to_json, split_scenes, write_script,
)
from reels.service import PLAN_JOB, RENDER_JOB
from reels.vision import describe_image
from reels.voice import reading_timings, synthesize
from subscription.service import SubscriptionService
from subtitle_styling.ass_generator import AssGenerator
from transcription.groq_whisper import GroqWhisperTranscriber
from transcription.language import normalize_language
from transcription.transliterate import romanize_transcript, wants_roman
from transcription.word_timing import clean_word_timings
from usage.context import llm_scope

log = get_logger(__name__)

# Mixed languages are spoken, and transcribed, as their base language.
_SPOKEN = {"hinglish": "hi", "tenglish": "te"}
_IMAGE_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_PARALLEL_SCENES = 3


def spoken_language(language: str) -> str:
    return _SPOKEN.get(language, normalize_language(language) or "en")


async def _load(reel_id: str) -> ReelProject | None:
    async with AsyncSessionLocal() as session:
        return await session.get(ReelProject, reel_id)


async def _save(reel_id: str, **fields) -> None:
    async with AsyncSessionLocal() as session:
        reel = await session.get(ReelProject, reel_id)
        for key, value in fields.items():
            setattr(reel, key, value)
        await session.commit()


@handler(PLAN_JOB)
async def plan_reel(job: Job) -> None:
    reel_id, user_id = job.payload["reel_id"], job.payload["user_id"]
    try:
        with llm_scope(user_id=user_id, step="reel_planning"):
            await _plan(reel_id, user_id)
    except Exception as exc:
        log.exception("Reel planning failed: reel=%s", reel_id)
        await _save(reel_id, status=ReelStatus.FAILED, error=f"Planning failed: {exc}"[:500])


async def _plan(reel_id: str, user_id: str) -> None:
    settings = get_settings()
    s3 = S3()
    reel = await _load(reel_id)
    async with AsyncSessionLocal() as session:
        is_pro = (await SubscriptionService.for_session(session).get_entitlements(user_id)).pro_ai_provider
    client = get_text_client(is_pro=is_pro, step="director")
    script = (reel.script or "").strip() or await write_script(reel.topic or reel.title, reel.language, client)
    language = spoken_language(reel.language)

    images = json.loads(reel.images)
    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)

        async def describe(image: dict) -> dict:
            if image.get("description"):
                return image
            local = work / Path(image["key"]).name
            await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, image["key"], str(local))
            media_type = _IMAGE_TYPES.get(local.suffix, "image/jpeg")
            return {**image, **await describe_image(local.read_bytes(), media_type, is_pro)}

        images = list(await asyncio.gather(*(describe(i) for i in images)))
        words = await _voice_words(reel, script, language, work, s3)

    segments = [{"text": " ".join(w["word"] for w in words), "words": words}]
    if wants_roman("auto", segments):
        await romanize_transcript(segments, get_text_client(is_pro=is_pro, step="transliteration"))
        words = segments[0]["words"]

    scenes = await assign_visuals(split_scenes(words), images, client)
    await _match_footage(scenes, images, user_id)
    avoid_repeats(scenes, images)
    duration = words[-1]["end"] + 0.4 if words else 0.0
    if scenes:
        scenes[-1].end = duration
    await _save(
        reel_id, script=script, images=json.dumps(images), words=json.dumps(words, ensure_ascii=False),
        scenes=scenes_to_json(scenes), duration_s=round(duration, 3), status=ReelStatus.READY, error=None,
    )
    log.info("Reel planned: reel=%s scenes=%d duration=%.1fs", reel_id, len(scenes), duration)


async def _voice_words(reel: ReelProject, script: str, language: str, work: Path, s3: S3) -> list[dict]:
    """Word timings from the uploaded voiceover, else from synthesised speech, else at reading pace."""
    settings = get_settings()
    audio = work / "voice.wav"
    if reel.voiceover_key:
        uploaded = work / f"upload{Path(reel.voiceover_key).suffix}"
        await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, reel.voiceover_key, str(uploaded))
        audio = uploaded
    elif await synthesize(script, language, None, audio):
        key = f"reels/{reel.user_id}/{reel.id}/voice.wav"
        await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, key, str(audio), "audio/wav")
        await _save(reel.id, voiceover_key=key)
    else:
        return reading_timings(script)
    duration = (await probe(str(audio))).duration
    segments, _ = await GroqWhisperTranscriber().transcribe(str(audio), duration, language, prompt=script[:500])
    return clean_word_timings([w for s in segments for w in s.get("words") or []])


async def _match_footage(scenes: list[Scene], images: list[dict], user_id: str) -> None:
    """Pick library shots for B-roll scenes; a scene with no good match falls back to an image or text."""
    footage = [s for s in scenes if s.kind == "broll"]
    if not footage:
        return
    async with AsyncSessionLocal() as session:
        picks = await BrollRetriever(BrollRepository(session), get_embedder()).find(
            [SceneQuery(f"{s.query} {s.subject}".strip(), s.duration) for s in footage], user_id=user_id,
        )
    for scene, pick in zip(footage, picks):
        if pick.best and good_match(pick.best, scene.subject):
            scene.asset_id = pick.best.asset.id
            scene.alternates = [p.asset.id for p in pick.ranked[1:]]
        else:
            fallback_image(scene, images, [], None)


@handler(RENDER_JOB)
async def render_reel(job: Job) -> None:
    reel_id, user_id, credits = job.payload["reel_id"], job.payload["user_id"], job.payload["credits"]
    try:
        await _render(reel_id, user_id)
    except Exception as exc:
        log.exception("Reel render failed: reel=%s", reel_id)
        await _save(reel_id, status=ReelStatus.FAILED, error=f"Render failed: {exc}"[:500], credits_charged=0)
        async with AsyncSessionLocal() as session:
            await SubscriptionService.for_session(session).refund_credits(
                user_id=user_id, amount=credits, reason=f"Reel render failed, refund for {reel_id}",
                reference_id=reel_id, reference_type="reel_render_refund",
            )


async def _render(reel_id: str, user_id: str) -> None:
    settings = get_settings()
    s3 = S3()
    reel = await _load(reel_id)
    scenes = scenes_from_json(reel.scenes)
    images = json.loads(reel.images)
    words = json.loads(reel.words)
    style = reel_render.style_for(reel.style)
    async with AsyncSessionLocal() as session:
        entitlements = await SubscriptionService.for_session(session).get_entitlements(user_id)
        assets = {a.id: a for a in await BrollRepository(session).get_many([s.asset_id for s in scenes if s.asset_id])}

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        fetched: dict[str, Path] = {}

        async def fetch(key: str) -> Path:
            if key not in fetched:
                local = work / f"src{len(fetched)}{Path(key).suffix}"
                fetched[key] = local
                await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, key, str(local))
            return fetched[key]

        slots = asyncio.Semaphore(MAX_PARALLEL_SCENES)

        async def scene_part(index: int, scene: Scene) -> Path:
            out = work / f"scene{index:03d}.mp4"
            async with slots:
                asset = assets.get(scene.asset_id or "")
                if scene.kind == "broll" and asset and asset.vertical_key:
                    await reel_render.run(reel_render.footage_cmd(await fetch(asset.vertical_key), scene.duration, out))
                elif scene.kind == "image" and scene.image_index is not None and scene.image_index < len(images):
                    path = await fetch(images[scene.image_index]["key"])
                    await reel_render.run(reel_render.still_cmd(path, scene.duration, out, blur_fill=True))
                else:
                    card = reel_render.text_card(scene.headline or scene.text, style, work / f"card{index}.png")
                    await reel_render.run(reel_render.still_cmd(card, scene.duration, out, blur_fill=False))
            return out

        parts = list(await asyncio.gather(*(scene_part(i, s) for i, s in enumerate(scenes))))
        voice = await fetch(reel.voiceover_key) if reel.voiceover_key else None
        joined = work / "joined.mp4"
        await reel_render.join(parts, voice, joined)

        ass_file = None
        if words:
            ass_file = work / "captions.ass"
            caption_words = [{"start": w["start"], "end": w["end"], "text": w["word"]} for w in words]
            ass_file.write_text(AssGenerator().build_ass(caption_words, 0.0, reel.duration_s, width=1080, height=1920), encoding="utf-8")
        final = await reel_render.finish(joined, ass_file, entitlements.watermark_forced, work / "reel.mp4")

        key = f"reels/{user_id}/{reel_id}/reel.mp4"
        await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, key, str(final), "video/mp4")
    await _save(reel_id, output_key=key, status=ReelStatus.DONE, error=None)
    log.info("Reel rendered: reel=%s scenes=%d", reel_id, len(scenes))
