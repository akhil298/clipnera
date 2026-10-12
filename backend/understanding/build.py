"""Build one asset's MUD from a local copy of the file.

Reuses the footage reel's perception (probe, shots, quality, faces), its shot
captions and Groq Whisper, then adds what those don't give (MEDIA_INVENTORY.md).
One analyzer failing leaves its fields empty and is noted in ``analyzers``;
only an unreadable file fails the build.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from core.logging_config import get_logger
from edit_engine import perception, story, vision
from transcription.groq_whisper import GroqWhisperTranscriber
from transcription.word_timing import clean_word_timings
from understanding import analyzers
from understanding.mud import MUD, Shot, Utterance, Word, check_mud

log = get_logger(__name__)

# The steps of a build, in order; the studio shows which one is running.
STAGES = ("shots", "transcript", "music", "moments")
StageHook = Callable[[str], Awaitable[None]]


async def build_mud(path: str, asset_id: str, kind: str, *, is_pro: bool, workdir: Path,
                    on_stage: StageHook | None = None) -> MUD:
    async def stage(name: str) -> None:
        if on_stage:
            await on_stage(name)

    if kind == "image":
        return MUD(asset_id=asset_id, kind="image", duration=0.0, analyzers={"probe": "skipped"})
    info = await perception.probe_media(path)
    if info.duration <= 0 or not (info.has_video or info.has_audio):
        raise ValueError("This file has no video or sound we can read.")
    duration = round(info.duration, 3)
    mud = MUD(asset_id=asset_id, kind="video" if info.has_video else "audio", duration=duration,
              width=info.width or None, height=info.height or None, has_audio=info.has_audio,
              analyzers={"probe": "ok"})

    raw_shots: list[dict[str, Any]] = []
    if info.has_video:
        await stage("shots")
        raw_shots = await _run(mud, "shots", lambda: _shots(path, info, is_pro)) or []
    audio = workdir / f"{asset_id}.wav"
    if info.has_audio and await _run(mud, "audio", lambda: perception.extract_audio(path, str(audio))) is not False:
        await stage("transcript")
        words, language = await _run(mud, "transcript", lambda: _transcribe(str(audio), duration)) or ([], None)
        mud.language = language
        mud.words = analyzers.tag_fillers(words)
        mud.utterances = _utterances(mud.words)
        mud.silences = analyzers.find_silences(mud.words, duration)
        speech = sum(u.t1 - u.t0 for u in mud.utterances)
        mud.speech_ratio = round(min(1.0, speech / duration), 3)
        if mud.kind == "audio" and mud.speech_ratio < analyzers.MUSIC_SPEECH_RATIO:
            await stage("music")
            beats_and_music = await _run(mud, "music", lambda: asyncio.to_thread(analyzers.analyze_music, str(audio)))
            if beats_and_music:
                mud.beats, mud.music = beats_and_music

    await stage("moments")
    shots = [_shot(n, raw, duration, len(raw_shots)) for n, raw in enumerate(raw_shots)]
    mud.scenes, mud.shots = analyzers.group_scenes(shots, mud.utterances, mud.silences, duration)
    mud.quality = analyzers.quality_ranges(mud.shots)
    mud.moments = analyzers.find_moments(mud.utterances, mud.shots)
    check_mud(mud)
    return mud


async def _run(mud: MUD, name: str, work: Callable[[], Awaitable[Any]]) -> Any:
    """Run one analyzer; a failure is logged and recorded, and returns False."""
    try:
        result = await work()
    except Exception:
        log.exception("Analyzer %s failed on asset %s", name, mud.asset_id)
        mud.analyzers[name] = "failed"
        return False
    mud.analyzers[name] = "ok"
    return result


async def _shots(path: str, info: perception.MediaInfo, is_pro: bool) -> list[dict[str, Any]]:
    frames = await perception.sample_frames(path, info)
    found = await asyncio.to_thread(perception.detect_shots, frames, info.duration)
    await asyncio.to_thread(perception.add_faces, found)
    shots = [{**shot.as_dict(), "frame": shot.frame} for shot in found]
    chosen = vision.shots_to_caption(shots, is_pro)
    captions = await vision.caption_shots([shots[i]["frame"] for i in chosen])
    for index, caption in zip(chosen, captions):
        shots[index]["caption"] = caption or None
    return shots


def _shot(n: int, raw: dict[str, Any], duration: float, count: int) -> Shot:
    # The last shot ends at the end of the file, so shots tile it exactly.
    end = duration if n == count - 1 else min(duration, raw["end"])
    return Shot(
        id=f"sh{n:04d}", t0=round(min(raw["start"], duration), 3), t1=round(end, 3), scene_id="",
        caption=raw.get("caption"), usable=raw["usable"], flags=analyzers.shot_flags(raw),
        blur=raw["blur"], brightness=raw["brightness"], motion=raw["motion"], faces=raw["faces"], face_x=raw["face_x"],
    )


async def _transcribe(audio: str, duration: float) -> tuple[list[Word], str | None]:
    segments, language = await GroqWhisperTranscriber().transcribe(audio, duration)
    timed = clean_word_timings([w for s in segments for w in s.get("words") or []])
    words = [
        Word(i=i, t0=min(w["start"], duration), t1=min(w["end"], duration), text=str(w["word"]).strip(),
             conf=round(float(w["probability"]), 3) if w.get("probability") is not None else None)
        for i, w in enumerate(w for w in timed if str(w.get("word", "")).strip())
    ]
    return words, language or None


def _utterances(words: list[Word]) -> list[Utterance]:
    sentences = story.sentences_from_words([{"src": 0, "word": w.text, "start": w.t0, "end": w.t1} for w in words])
    return [Utterance(id=f"u{n:04d}", t0=round(s["start"], 3), t1=round(s["end"], 3), w0=s["w0"], w1=s["w1"],
                      text=s["text"]) for n, s in enumerate(sentences)]
