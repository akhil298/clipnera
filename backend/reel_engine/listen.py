"""Listen: what the audio is (voice, song, voice over a song, silence) and every spoken word.

The audio kind decides the whole edit, so two signals must agree: the stem levels (a voice/music
separation measured on sample windows) and the transcript (how much of the time is speech, and
whether it reads as lyrics). Words are transcribed per source, romanized where the product
captions in Roman script, and fillers are tagged for the clean pass.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from pathlib import Path

import numpy as np

from core.logging_config import get_logger
from reel_engine.media import read_wav, rms_db, run
from reel_engine.plan import AudioReport, Source, Word

log = get_logger(__name__)

SEPARATION_RATE = 44100
CHUNK_SECONDS = 20.0
OVERLAP_SECONDS = 1.0
SAMPLE_WINDOWS = 3
# Speech must cover this share of the audio before it counts as someone talking.
SPEECH_COVERAGE = 0.12
# Music this close to the voice level (dB) is a song under the voice, not room tone.
MUSIC_UNDER_VOICE_DB = 12.0
SILENT_DB = -45.0


# ------------------------------------------------------------------ voice / music separation

def _model():
    from torchaudio.pipelines import HDEMUCS_HIGH_MUSDB_PLUS

    return HDEMUCS_HIGH_MUSDB_PLUS.get_model().eval()


def separate(mix_wav: Path, voice_out: Path, music_out: Path | None = None) -> bool:
    """Split ``mix_wav`` (44.1 kHz stereo) into voice and music stems, chunk by chunk with crossfades.

    Returns False when the separator is unavailable; callers then use the mix as the voice.
    """
    try:
        import torch
        import torchaudio
    except ImportError:
        return False
    model = _model()
    vocals = model.sources.index("vocals")
    wav, rate = torchaudio.load(str(mix_wav))
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    chunk, overlap = int(CHUNK_SECONDS * rate), int(OVERLAP_SECONDS * rate)
    voice = torch.zeros_like(wav)
    weight = torch.zeros(wav.shape[1])
    fade = torch.linspace(0, 1, overlap) if overlap else torch.ones(0)
    start = 0
    with torch.no_grad():
        while start < wav.shape[1]:
            end = min(wav.shape[1], start + chunk)
            piece = wav[:, start:end]
            ref = piece.mean(0)
            std = ref.std() if ref.std() > 1e-6 else torch.tensor(1.0)
            stems = model(((piece - ref.mean()) / std)[None])[0] * std + ref.mean()
            window = torch.ones(end - start)
            if start > 0 and overlap:
                window[:overlap] = fade[: end - start][:overlap]
            if end < wav.shape[1] and overlap:
                window[-overlap:] = torch.minimum(window[-overlap:], fade.flip(0))
            voice[:, start:end] += stems[vocals] * window
            weight[start:end] += window
            if end == wav.shape[1]:
                break
            start = end - overlap
    voice = voice / weight.clamp(min=1e-6)
    torchaudio.save(str(voice_out), voice, rate)
    if music_out is not None:
        torchaudio.save(str(music_out), wav - voice, rate)
    return True


def stem_levels(path: Path, duration: float, work: Path) -> tuple[float, float]:
    """Voice and music level (dB) measured on a few sample windows of the source."""
    windows = [duration * (k + 0.5) / SAMPLE_WINDOWS for k in range(SAMPLE_WINDOWS)] if duration > CHUNK_SECONDS * 1.5 else [duration / 2]
    voice_db, music_db = [], []
    for k, centre in enumerate(windows):
        start = max(0.0, centre - CHUNK_SECONDS / 2)
        mix = work / f"lvl{k}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{min(CHUNK_SECONDS, duration):.2f}", "-i", str(path),
             "-vn", "-ac", "2", "-ar", str(SEPARATION_RATE), str(mix)])
        voice, music = work / f"lvl{k}_v.wav", work / f"lvl{k}_m.wav"
        if not separate(mix, voice, music):
            samples, _ = read_wav(mix)
            return rms_db(samples), -90.0
        voice_db.append(rms_db(read_wav(voice)[0]))
        music_db.append(rms_db(read_wav(music)[0]))
    return float(np.max(voice_db)), float(np.median(music_db))


# ------------------------------------------------------------------ words

def lyrics_score(words: list[Word]) -> float:
    """How much the transcript repeats itself line by line, as lyrics do (0 = never, 1 = all)."""
    text = " ".join(w.text.lower() for w in words)
    grams = [tuple(g) for g in zip(*(re.findall(r"[\w']+", text)[k:] for k in range(4)))]
    if len(grams) < 12:
        return 0.0
    counts = Counter(grams)
    return sum(c for c in counts.values() if c > 1) / len(grams)


async def transcribe(source: Source, work: Path) -> tuple[list[Word], str]:
    from transcription.groq_whisper import GroqWhisperTranscriber
    from transcription.word_timing import clean_word_timings

    audio = work / f"src{source.index}_16k.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", source.path, "-vn", "-ac", "1", "-ar", "16000", str(audio)])
    segments, language = await GroqWhisperTranscriber().transcribe(str(audio), source.duration, None)
    raw = clean_word_timings([w for s in segments for w in s.get("words") or []])
    words = [Word(i=0, src=source.index, t0=round(float(w["start"]), 3), t1=round(float(w["end"]), 3), text=str(w["word"]).strip())
             for w in raw if str(w["word"]).strip()]
    return words, language or ""


async def romanize(words: list[Word]) -> None:
    """Hindi, Telugu and the other Indic scripts captioned in Roman letters, as the rest of the product does."""
    from clients.ai import get_text_client
    from transcription.transliterate import romanize_transcript, wants_roman

    group = [{"text": " ".join(w.text for w in words), "words": [{"word": w.text, "start": w.t0, "end": w.t1} for w in words]}]
    if words and wants_roman("auto", group):
        await romanize_transcript(group, get_text_client(is_pro=True, step="transliteration"))
        for word, spelled in zip(words, group[0]["words"]):
            word.text = str(spelled["word"]).strip() or word.text


def tag_fillers(words: list[Word]) -> None:
    from understanding.analyzers import tag_fillers as tag
    from understanding.mud import Word as MudWord

    tagged = tag([MudWord(i=k, t0=w.t0, t1=w.t1, text=w.text) for k, w in enumerate(words)])
    for word, mud in zip(words, tagged):
        word.filler = mud.filler is not None


# ------------------------------------------------------------------ the agent

def classify(coverage: float, lyrics: float, voice_db: float, music_db: float) -> tuple[str, str]:
    if coverage < SPEECH_COVERAGE or lyrics > 0.35:
        if max(voice_db, music_db) < SILENT_DB:
            return "silent", "no speech and almost no sound"
        why = f"lyrics-like repetition {lyrics:.0%}" if lyrics > 0.35 else f"speech covers only {coverage:.0%}"
        return "song", f"{why}; music at {music_db:.0f} dB"
    if music_db > voice_db - MUSIC_UNDER_VOICE_DB and music_db > SILENT_DB:
        return "voice_song", f"speech covers {coverage:.0%}, music {music_db:.0f} dB under a voice at {voice_db:.0f} dB"
    return "voice", f"speech covers {coverage:.0%}; music at {music_db:.0f} dB is room tone"


async def listen(sources: list[Source], work: Path) -> AudioReport:
    talking = [s for s in sources if s.kind == "video" and s.has_audio] + [s for s in sources if s.kind == "audio"]
    if not talking:
        return AudioReport(kind="silent", why="no source has audio")
    results = await asyncio.gather(*(transcribe(s, work) for s in talking))
    words: list[Word] = []
    language = ""
    for (found, lang), source in zip(results, talking):
        words += found
        language = language or lang
    for k, word in enumerate(words):
        word.i = k
    levels = [await asyncio.to_thread(stem_levels, Path(s.path), s.duration, work) for s in talking]
    voice_db = max(v for v, _ in levels)
    music_db = max(m for _, m in levels)
    total = sum(s.duration for s in talking) or 1.0
    coverage = sum(w.t1 - w.t0 for w in words) / total
    lyrics = lyrics_score(words)
    kind, why = classify(coverage, lyrics, voice_db, music_db)
    if kind in ("voice", "voice_song"):
        await romanize(words)
        tag_fillers(words)
    else:
        words = []
    log.info("Listen: %s (%s)", kind, why)
    return AudioReport(kind=kind, voice_db=round(voice_db, 1), music_db=round(music_db, 1), lyrics=lyrics > 0.35,
                       language=language, words=words, why=why)
