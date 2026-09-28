"""The footage reel's background jobs: analyse and plan, re-plan, and render.

Each handler is safe to run again after a crash: it reads the edit, does its
work from the S3 sources, and writes whole JSON documents back. Heavy work is
FFmpeg and OpenCV on CPU; the AI calls are transcription, contact-sheet
captions and one director call.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from broll.renditions import run
from clients.ai import get_text_client
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from edit_engine import director, perception, render, story, vision
from edit_engine.compiler import compile_timeline, layout_for
from edit_engine.limits import limits_for
from edit_engine.model import EditProject, EditStatus, MusicStatus, MusicTrack
from edit_engine.music import pick_track
from edit_engine.pricing import reel_credits, rerender_credits
from edit_engine.script import align, coverage, resolve_mode, script_lines, unscripted
from feature_flags.registry import REEL_EDITOR_OPUS
from feature_flags.service import FeatureFlagService
from jobs.queue import Job, get_queue, handler
from notifications.service import notify_reel_outcome
from reels.jobs import spoken_language
from reels.vision import describe_image
from reels.voice import reading_timings, synthesize
from sqlalchemy import select
from subscription.service import SubscriptionService
from transcription.groq_whisper import GroqWhisperTranscriber
from transcription.transliterate import romanize_transcript, wants_roman
from transcription.word_timing import clean_word_timings
from usage.context import llm_scope

log = get_logger(__name__)

ANALYZE_JOB = "edits.analyze"
PLAN_JOB = "edits.plan"
RENDER_JOB = "edits.render"
ANALYSIS_VERSION = 1
PARALLEL_DOWNLOADS = 3
_IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


async def load(edit_id: str) -> EditProject | None:
    async with AsyncSessionLocal() as session:
        return await session.get(EditProject, edit_id)


async def save(edit_id: str, **fields: Any) -> None:
    async with AsyncSessionLocal() as session:
        edit = await session.get(EditProject, edit_id)
        for key, value in fields.items():
            setattr(edit, key, value)
        await session.commit()


async def progress(edit_id: str, message: str) -> None:
    analysis = json.loads((await load(edit_id)).analysis or "{}")
    await save(edit_id, analysis=json.dumps({**analysis, "progress": message}))


# --- analyse ------------------------------------------------------------------

@handler(ANALYZE_JOB)
async def analyze_edit(job: Job) -> None:
    edit_id, user_id = job.payload["edit_id"], job.payload["user_id"]
    try:
        with llm_scope(user_id=user_id, project_id=edit_id, step="reel_analysis"):
            await _analyze(edit_id, user_id)
    except Exception as exc:
        log.exception("Footage analysis failed: edit=%s", edit_id)
        await save(edit_id, status=EditStatus.FAILED, error=_friendly(exc, "We couldn't read your footage"))


def _friendly(exc: Exception, prefix: str) -> str:
    detail = str(exc) if isinstance(exc, ValueError) else "please try again, or try other files"
    return f"{prefix}: {detail}"[:500]


async def _download(sources: list[dict[str, Any]], work: Path, s3: S3) -> dict[int, Path]:
    bucket = get_settings().S3_BUCKET_NAME
    slots = asyncio.Semaphore(PARALLEL_DOWNLOADS)

    async def fetch(index: int, source: dict[str, Any]) -> tuple[int, Path]:
        local = work / f"src{index}{Path(source['key']).suffix}"
        async with slots:
            await asyncio.to_thread(s3.download_file, bucket, source["key"], str(local))
        return index, local

    return dict(await asyncio.gather(*(fetch(i, s) for i, s in enumerate(sources))))


async def _analyze(edit_id: str, user_id: str) -> None:
    settings = get_settings()
    s3 = S3()
    edit = await load(edit_id)
    async with AsyncSessionLocal() as session:
        entitlements = await SubscriptionService.for_session(session).get_entitlements(user_id)
    is_pro = entitlements.pro_ai_provider
    limits = limits_for(entitlements)
    sources = [s for s in json.loads(edit.sources) if s.get("uploaded")]
    language = spoken_language(edit.language)
    prompt = (edit.script or "")[:500] or None

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        await progress(edit_id, "Reading your clips")
        local = await _download(sources, work, s3)
        raw_seconds = 0.0
        words: list[dict[str, Any]] = []
        shots: list[dict[str, Any]] = []
        shot_frames = []
        photos: list[dict[str, Any]] = []
        voice_index: int | None = None
        for index, source in enumerate(sources):
            path = str(local[index])
            if source["kind"] == "voice":
                voice_index = index
                continue
            if source["kind"] == "image":
                if not source.get("description"):
                    media_type = _IMAGE_TYPES.get(local[index].suffix.lower(), "image/jpeg")
                    source.update(await describe_image(local[index].read_bytes(), media_type, is_pro))
                photos.append({"id": f"p{len(photos)}", "src": index, "description": source.get("description", "")})
                continue
            info = await perception.probe_media(path)
            if not info.has_video or info.duration <= 0:
                raise ValueError(f"{source['name']} is not a video we can read")
            raw_seconds += info.duration
            if raw_seconds > limits.max_raw_seconds + 1:
                raise ValueError(f"your plan edits up to {limits.max_raw_seconds // 60} minutes of footage per reel")
            source.update(duration=round(info.duration, 3), width=info.width, height=info.height, has_audio=info.has_audio)
            frames = await perception.sample_frames(path, info)
            found = await asyncio.to_thread(perception.detect_shots, frames, info.duration)
            await asyncio.to_thread(perception.add_faces, found)
            for shot in found:
                shots.append({"id": f"v{len(shots)}", "src": index, **shot.as_dict()})
                shot_frames.append(shot.frame)
            proxy = work / f"proxy{index}.mp4"
            await run(perception.proxy_cmd(path, str(proxy), info))
            source["proxy_key"] = f"{Path(source['key']).with_suffix('')}_proxy.mp4"
            await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, source["proxy_key"], str(proxy), "video/mp4")
            if info.has_audio:
                audio = work / f"audio{index}.wav"
                await perception.extract_audio(path, str(audio))
                segments, _ = await GroqWhisperTranscriber().transcribe(str(audio), info.duration, language, prompt=prompt)
                words += [{**w, "src": index} for w in clean_word_timings([w for s in segments for w in s.get("words") or []])]

        await progress(edit_id, "Listening to what you said")
        words = await _romanized(words, is_pro)
        voice_words = await _voice_words(edit, sources, local, voice_index, bool(words), language, work, s3)

        await progress(edit_id, "Finding the best takes")
        captioned = vision.shots_to_caption(shots, is_pro)
        captions = await vision.caption_shots([shot_frames[i] for i in captioned])
        for i, caption in zip(captioned, captions):
            shots[i]["caption"] = caption

    sentences = story.sentences_from_words(words)
    groups = story.retake_groups(sentences)
    speech_seconds = sum(s["end"] - s["start"] for s in sentences)
    analysis: dict[str, Any] = {
        "version": ANALYSIS_VERSION, "language": edit.language, "words": words, "sentences": sentences,
        "retakes": groups, "dropped": sorted(story.dropped_takes(sentences, groups)), "shots": shots, "photos": photos,
        "content_type": story.classify(speech_seconds, raw_seconds, shots, voice_words is not None),
    }
    if voice_words is not None:
        analysis["voice_words"] = voice_words["words"]
        analysis["voice_sentences"] = [{**s, "id": f"o{n}"} for n, s in enumerate(story.sentences_from_words(
            [{**w, "src": -1} for w in voice_words["words"]]))]
        analysis["voiceover_src"] = voice_words["src"]
    await save(edit_id, sources=json.dumps(voice_words["sources"] if voice_words else sources, ensure_ascii=False),
               analysis=json.dumps(analysis, ensure_ascii=False), raw_seconds=round(raw_seconds, 3))
    await _plan(edit_id, user_id)


async def _romanized(words: list[dict[str, Any]], is_pro: bool) -> list[dict[str, Any]]:
    """Hindi and Telugu speech captioned in Roman script, as the rest of the product does."""
    segments = [{"text": " ".join(str(w["word"]) for w in words), "words": words}]
    if words and wants_roman("auto", segments):
        await romanize_transcript(segments, get_text_client(is_pro=is_pro, step="transliteration"))
    return segments[0]["words"]


async def _voice_words(edit: EditProject, sources: list[dict[str, Any]], local: dict[int, Path], voice_index: int | None,
                       has_speech: bool, language: str, work: Path, s3: S3) -> dict[str, Any] | None:
    """The voiceover's words, if this reel has one: an uploaded recording, else synthetic speech of the script.

    Returns the words, the voiceover's source index (None when captions run at
    reading pace with no audio) and the source list, which gains an entry for
    synthesised speech.
    """
    script = (edit.script or "").strip()
    requested = edit.script_mode
    wants_voiceover = voice_index is not None or (script and (requested == "voiceover" or (requested == "auto" and not has_speech)))
    if not wants_voiceover:
        return None
    if voice_index is not None:
        path = local[voice_index]
    else:
        path = work / "voice.wav"
        if not await synthesize(script, language, None, path):
            return {"words": reading_timings(script), "src": None, "sources": sources}
        key = f"edits/{edit.user_id}/{edit.id}/voice.wav"
        await asyncio.to_thread(s3.upload_file, get_settings().S3_BUCKET_NAME, key, str(path), "audio/wav")
        sources = [*sources, {"key": key, "kind": "voice", "name": "AI voiceover", "content_type": "audio/wav", "uploaded": True}]
        voice_index = len(sources) - 1
    info = await perception.probe_media(str(path))
    segments, _ = await GroqWhisperTranscriber().transcribe(str(path), info.duration, language, prompt=script[:500] or None)
    sources[voice_index]["duration"] = round(info.duration, 3)
    return {"words": clean_word_timings([w for s in segments for w in s.get("words") or []]), "src": voice_index, "sources": sources}


# --- plan ---------------------------------------------------------------------

@handler(PLAN_JOB)
async def plan_edit(job: Job) -> None:
    edit_id, user_id = job.payload["edit_id"], job.payload["user_id"]
    try:
        with llm_scope(user_id=user_id, project_id=edit_id, step="reel_director"):
            await _plan(edit_id, user_id)
    except Exception as exc:
        log.exception("Footage planning failed: edit=%s", edit_id)
        await save(edit_id, status=EditStatus.FAILED, error=_friendly(exc, "We couldn't plan your reel"))


async def _plan(edit_id: str, user_id: str) -> None:
    edit = await load(edit_id)
    analysis = json.loads(edit.analysis)
    async with AsyncSessionLocal() as session:
        entitlements = await SubscriptionService.for_session(session).get_entitlements(user_id)
        opus = await FeatureFlagService(session).is_enabled(REEL_EDITOR_OPUS)
    is_pro = entitlements.pro_ai_provider
    limits = limits_for(entitlements)
    await progress(edit_id, "Planning the edit")

    script = (edit.script or "").strip()
    lines = script_lines(script) if script else []
    dropped = set(analysis.get("dropped") or [])
    aligned = align(lines, analysis["sentences"], dropped) if lines and analysis["sentences"] else \
        [{"text": line, "sentences": [], "score": 0.0} for line in lines]
    if analysis.get("voice_words") is not None:
        mode = "voiceover"
    else:
        mode = resolve_mode(edit.script_mode, bool(lines), bool(analysis["sentences"]), coverage(aligned))
        if mode == "voiceover":
            # The creator asked for a voiceover after analysis made none; plan it as notes on screen instead.
            mode = "onscreen"
    fixed = [i for line in aligned for i in line["sentences"]] if mode == "spoken" else None

    client = director.director_client(is_pro, opus)
    log_text = director.footage_log(analysis, mode, script, edit.intent, edit.target_seconds, limits.max_output_seconds, fixed)
    plan = director.validate(await director.direct(client, log_text), analysis, mode)
    plan.update(
        mode=mode, layout=layout_for(mode, bool(analysis["sentences"])), script_lines=aligned,
        caption_style=edit.caption_style, director_model=getattr(client, "model", ""),
        director_version=director.DIRECTOR_VERSION, restored=[], removed=[],
        unscripted=unscripted(aligned, analysis["sentences"], dropped) if mode == "spoken" else [],
    )
    plan["music"] = await choose_music(plan["music_mood"], plan["energy"], edit_id)
    timeline = compile_timeline(analysis, plan, size=limits.size, target_seconds=edit.target_seconds,
                                max_seconds=limits.max_output_seconds)
    analysis.pop("progress", None)
    await save(edit_id, plan=json.dumps(plan, ensure_ascii=False), timeline=json.dumps(timeline, ensure_ascii=False),
               analysis=json.dumps(analysis, ensure_ascii=False), duration_s=timeline["duration"], opus=is_pro and opus,
               title=edit.title if edit.title != "Untitled reel" else plan["title"], status=EditStatus.PLANNED, error=None)
    log.info("Footage reel planned: edit=%s mode=%s layout=%s duration=%.1fs", edit_id, mode, plan["layout"], timeline["duration"])
    if edit.autopilot and not edit.renders:
        await autopilot_render(edit_id, user_id)


async def choose_music(mood: str, energy: str, seed: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as session:
        tracks = list((await session.execute(select(MusicTrack).where(MusicTrack.status == MusicStatus.LIVE))).scalars())
    track = pick_track(tracks, mood, energy, seed)
    return track_choice(track) if track else None


def track_choice(track: MusicTrack) -> dict[str, Any]:
    return {"track_id": track.id, "bpm": track.bpm, "title": track.title, "artist": track.artist,
            "licence": track.licence, "credit_text": track.credit_text}


async def autopilot_render(edit_id: str, user_id: str) -> None:
    """Autopilot: charge and render straight after planning; if credits are short, leave the plan waiting."""
    edit = await load(edit_id)
    try:
        async with AsyncSessionLocal() as session:
            credits = await charge_render(SubscriptionService.for_session(session), user_id, edit)
    except Exception as exc:
        await save(edit_id, error=f"Your plan is ready. Autopilot didn't render it: {exc}"[:500])
        return
    await save(edit_id, status=EditStatus.RENDERING, credits_charged=edit.credits_charged + credits)
    await get_queue().enqueue(Job(RENDER_JOB, {"edit_id": edit_id, "user_id": user_id, "credits": credits}))


# --- render -------------------------------------------------------------------

@handler(RENDER_JOB)
async def render_edit(job: Job) -> None:
    edit_id, user_id, credits = job.payload["edit_id"], job.payload["user_id"], job.payload["credits"]
    try:
        await _render(edit_id, user_id)
    except Exception as exc:
        log.exception("Footage reel render failed: edit=%s", edit_id)
        edit = await load(edit_id)
        await save(edit_id, status=EditStatus.PLANNED if not edit.output_key else EditStatus.DONE,
                   error=_friendly(exc, "The render failed and your credits were refunded"),
                   credits_charged=max(0, edit.credits_charged - credits))
        async with AsyncSessionLocal() as session:
            await SubscriptionService.for_session(session).refund_credits(
                user_id=user_id, amount=credits, reason=f"Footage reel render failed, refund for {edit_id}",
                reference_id=edit_id, reference_type="edit_render_refund",
            )
        await notify_reel_outcome(user_id, edit.title, success=False)


async def _render(edit_id: str, user_id: str) -> None:
    settings = get_settings()
    s3 = S3()
    edit = await load(edit_id)
    timeline = json.loads(edit.timeline)
    sources = json.loads(edit.sources)
    async with AsyncSessionLocal() as session:
        entitlements = await SubscriptionService.for_session(session).get_entitlements(user_id)
        track = await session.get(MusicTrack, (timeline.get("music") or {}).get("track_id") or "")
    if track is not None and track.status != MusicStatus.LIVE:
        # A track pulled since planning never reaches a render.
        timeline["music"], track = None, None
    used = {item["src"] for item in timeline["picture"] if item.get("src") is not None}
    used |= {piece["src"] for piece in timeline["voice"]}
    if timeline.get("voiceover"):
        used.add(timeline["voiceover"]["src"])

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        fetched = await _download([sources[i] for i in sorted(used)], work, s3)
        local = {src: fetched[n] for n, src in enumerate(sorted(used))}
        music = None
        if track is not None:
            music = work / f"music{Path(track.audio_key).suffix}"
            await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, track.audio_key, str(music))
        final = await render.render(timeline, local, music, entitlements.watermark_forced, work)
        key = f"edits/{user_id}/{edit_id}/reel.mp4"
        await asyncio.to_thread(s3.upload_file, settings.S3_BUCKET_NAME, key, str(final), "video/mp4")

    credit = json.dumps(track_choice(track), ensure_ascii=False) if track else None
    await save(edit_id, output_key=key, status=EditStatus.DONE, error=None, renders=edit.renders + 1, music_credit=credit)
    await notify_reel_outcome(user_id, edit.title, success=True)
    log.info("Footage reel rendered: edit=%s duration=%.1fs", edit_id, timeline["duration"])


async def charge_render(subscriptions: SubscriptionService, user_id: str, edit: EditProject) -> int:
    """Take the next render's credits and count it toward the daily cap; returns the credits taken.

    The cap is counted after the charge, so a render refused for credits doesn't
    use up the day's renders; a render refused by the cap is refunded.
    """
    credits = price(edit)
    await subscriptions.deduct_credits(user_id=user_id, amount=credits, reason=f"Footage reel: {edit.duration_s:.0f}s",
                                       reference_id=edit.id, reference_type="edit_render")
    try:
        await subscriptions.consume_daily_quota(user_id, "reel_renders")
    except Exception:
        await subscriptions.refund_credits(user_id=user_id, amount=credits, reason="Daily render limit reached",
                                           reference_id=edit.id, reference_type="edit_render_refund")
        raise
    return credits


def price(edit: EditProject) -> int:
    """Credits the next render of ``edit`` costs."""
    full = reel_credits(edit.duration_s, edit.raw_seconds, edit.opus)
    return rerender_credits(full) if edit.renders else full
