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
from transcription.local_whisper import transcribe_local
from transcription.word_timing import clean_word_timings
from understanding import analyzers, reading
from understanding.mud import MUD, Shot, Trim, Utterance, Word, check_mud

log = get_logger(__name__)

SUMMARY_CHARS = 240
TOPIC_CHARS = 40
WHY_CHARS = 80
# The most of the speech the reading's cuts may remove.
MAX_TRIMMED_SHARE = 0.35

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
    read = await _run(mud, "reading", lambda: reading.read_transcript(mud.utterances)) if mud.utterances else None
    if read:
        mud.summary, mud.topics = _plain(read.summary, SUMMARY_CHARS), [_plain(t, TOPIC_CHARS) for t in read.topics[:reading.MAX_TOPICS]]
    mud.moments = analyzers.find_moments(mud.utterances, mud.shots, _picks(read, mud.utterances) if read else ())
    mud.trims = _merge_trims([*(_trims(read, mud.utterances, duration) if read else []),
                              *analyzers.find_retakes(mud.utterances)])
    check_mud(mud)
    return mud


def _plain(text: str, limit: int) -> str:
    """One line of a model's words about untrusted speech: no line breaks to hide a second message in."""
    return " ".join(text.split())[:limit]


def _picks(read: reading.Reading, utterances: list[Utterance]) -> list[tuple[float, float, float, str]]:
    """The model's moments as (score, t0, t1, why); a pick naming lines that don't exist is dropped."""
    by_id = {u.id: u for u in utterances}
    picks = []
    for pick in read.moments[:reading.MAX_PICKS]:
        first, last = by_id.get(pick.first), by_id.get(pick.last)
        if first and last and first.t0 < last.t1:
            picks.append((pick.score, first.t0, last.t1, _plain(pick.why, WHY_CHARS) or "spoken line"))
    return picks


def _trims(read: reading.Reading, utterances: list[Utterance], duration: float) -> list[Trim]:
    """The model's cuts as time ranges. They may never add up to most of the recording: a reading that
    wants to throw away that much has misread it, and none of its cuts are trusted."""
    by_id = {u.id: u for u in utterances}
    trims = []
    for cut in read.cuts[:reading.MAX_CUTS]:
        first, last = by_id.get(cut.first), by_id.get(cut.last)
        if first and last and first.t0 < last.t1:
            trims.append(Trim(t0=first.t0, t1=last.t1, kind=cut.kind, why=_plain(cut.why, WHY_CHARS) or cut.kind))
    spoken = sum(u.t1 - u.t0 for u in utterances) or duration
    if sum(t.t1 - t.t0 for t in trims) > MAX_TRIMMED_SHARE * spoken:
        log.warning("The reading cut too much of the speech; ignoring its cuts")
        return []
    return sorted(trims, key=lambda t: t.t0)


def _merge_trims(trims: list[Trim]) -> list[Trim]:
    """One trim per stretch: the model's reading and the retake rule may both mark the same line."""
    merged: list[Trim] = []
    for trim in sorted(trims, key=lambda t: (t.t0, -t.t1)):
        if merged and trim.t0 < merged[-1].t1:
            merged[-1].t1 = max(merged[-1].t1, trim.t1)
            continue
        merged.append(trim)
    return merged


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
    segments, language = await _speech(audio, duration)
    timed = clean_word_timings([w for s in segments for w in s.get("words") or []])
    words = [
        Word(i=i, t0=min(w["start"], duration), t1=min(w["end"], duration), text=str(w["word"]).strip(),
             conf=round(float(w["probability"]), 3) if w.get("probability") is not None else None)
        for i, w in enumerate(w for w in timed if str(w.get("word", "")).strip())
    ]
    return words, language or None


async def _speech(audio: str, duration: float) -> tuple[list[dict[str, Any]], str]:
    """The hosted transcription, or this machine's when the hosted one has no key, fails or hears nothing."""
    if GroqWhisperTranscriber.available():
        try:
            segments, language = await GroqWhisperTranscriber().transcribe(audio, duration)
            if segments:
                return segments, language
        except Exception as exc:
            log.warning("Hosted transcription failed, transcribing on this machine: %s", exc)
    return await transcribe_local(audio)


def _utterances(words: list[Word]) -> list[Utterance]:
    sentences = story.sentences_from_words([{"src": 0, "word": w.text, "start": w.t0, "end": w.t1} for w in words])
    return [Utterance(id=f"u{n:04d}", t0=round(s["start"], 3), t1=round(s["end"], 3), w0=s["w0"], w1=s["w1"],
                      text=s["text"]) for n, s in enumerate(sentences)]
