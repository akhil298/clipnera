"""Compose Clipnera's own music beds into ``static/motion/music``.

Every track is written here: chords, bass, drums and melody parts played by oscillators,
filtered noise and envelopes (the building blocks of build_synth_sfx), so Clipnera owns it
outright: no licence to track, nothing for Content ID to match. Each style is a tempo, a key,
a chord progression, the parts that play and an arrangement (intro, verses, a break, an ending),
rendered with a fixed seed so a rebuild writes the same files.

``manifest.json`` lists each track with its mood, tags, tempo and length, for brain.library.

    cd backend && venv/bin/python scripts/build_synth_music.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motion.synth import SR, Signal, bass, clap, crackle, decay, hat, highpass, hz, keys, kick, lowpass, noise, pad, pluck, shaker, snare, tom  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "static" / "motion" / "music"
LICENCE = "Clipnera original, composed in code"
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
# Where the mix sits before export mastering: quiet enough to duck under a voice.
TARGET_RMS_DB = -18.0
PEAK = 10 ** (-1.0 / 20)



# ---------------------------------------------------------------- styles

@dataclass(frozen=True)
class Style:
    id: str
    name: str
    mood: str
    tags: tuple[str, ...]
    bpm: float
    # The key's tonic, in semitones from A4 (C4 = -9), and its scale.
    key: int
    minor: bool
    # Scale degrees, one chord a bar (1 = the tonic).
    progression: tuple[int, ...]
    # 16 steps a bar: x = hit, . = rest.
    kick: str
    snare: str
    hats: str
    # The part that plays the chords: "keys", "pluck" or "pad" only.
    lead: str
    # On which 16th steps the chord part plays (for keys and pluck).
    rhythm: tuple[int, ...]
    arpeggio: bool = False
    swing: float = 0.0
    vinyl: bool = False
    clap_on_snare: bool = False
    toms: bool = False
    # Sections: (bars, parts playing); parts are drums, bass, lead, pad.
    sections: tuple[tuple[int, frozenset[str]], ...] = ()


ALL = frozenset({"drums", "bass", "lead", "pad"})
SOFT = frozenset({"lead", "pad"})

STYLES = [
    Style("lofi_study", "Lo-fi Study", "lofi", ("lofi", "chill", "study", "cozy", "vlog", "cooking"), 82, -9, False,
          (2, 5, 1, 6), "x.....x...x.....", "....x.......x...", "x.x.x.x.x.x.x.x.", "keys", (0, 7, 10),
          swing=0.18, vinyl=True, sections=((4, SOFT), (8, ALL), (4, frozenset({"lead", "pad", "bass"})), (8, ALL), (2, SOFT))),
    Style("sunny_vlog", "Sunny Vlog", "upbeat", ("upbeat", "happy", "vlog", "day in the life", "food", "travel"), 112, -7, False,
          (1, 5, 6, 4), "x...x...x...x...", "....x.......x...", "..x...x...x...x.", "pluck", tuple(range(0, 16, 2)),
          arpeggio=True, clap_on_snare=True, sections=((4, frozenset({"lead", "pad"})), (8, ALL), (4, frozenset({"lead", "bass", "pad"})), (8, ALL), (2, SOFT))),
    Style("easy_morning", "Easy Morning", "chill", ("chill", "calm", "morning", "soft", "lifestyle"), 90, -4, False,
          (1, 6, 4, 5), "x.......x.......", "................", "....x.......x...", "keys", (0, 6, 12),
          sections=((4, SOFT), (8, frozenset({"lead", "pad", "bass", "drums"})), (8, ALL), (2, SOFT))),
    Style("big_reveal", "Big Reveal", "cinematic", ("cinematic", "epic", "inspiring", "reveal", "trailer"), 72, -12, True,
          (1, 6, 3, 7), "x...............", "................", "................", "pad", (0,),
          toms=True, sections=((4, frozenset({"pad"})), (4, frozenset({"pad", "bass"})), (8, ALL), (2, frozenset({"pad"})))),
    Style("ticking_clock", "Ticking Clock", "dramatic", ("tension", "suspense", "dramatic", "mystery"), 100, -10, True,
          (1, 1, 6, 5), "x.......x.......", "................", "x.x.x.x.x.x.x.x.", "pluck", tuple(range(16)),
          sections=((4, frozenset({"lead"})), (8, frozenset({"lead", "bass", "drums"})), (8, ALL), (2, frozenset({"lead"})))),
    Style("bright_pitch", "Bright Pitch", "corporate", ("corporate", "business", "tech", "explainer", "positive"), 108, -5, False,
          (1, 4, 6, 5), "x...x...x...x...", "....x.......x...", "x.x.x.x.x.x.x.x.", "pluck", tuple(range(0, 16, 2)),
          arpeggio=True, sections=((4, frozenset({"lead", "pad"})), (8, ALL), (8, ALL), (2, SOFT))),
    Style("silly_steps", "Silly Steps", "funny", ("funny", "playful", "comedy", "quirky", "kids"), 124, -2, False,
          (1, 4, 5, 1), "x.......x.......", "....x.......x...", "................", "keys", (0, 3, 6, 8, 11, 14),
          clap_on_snare=True, sections=((2, frozenset({"lead"})), (8, frozenset({"lead", "bass", "drums"})), (8, ALL), (2, frozenset({"lead"})))),
    Style("rise_up", "Rise Up", "inspiring", ("inspiring", "motivational", "uplifting", "growth", "story"), 96, -9, False,
          (6, 4, 1, 5), "x.......x.......", "....x.......x...", "x...x...x...x...", "keys", tuple(range(0, 16, 2)),
          arpeggio=True, sections=((4, frozenset({"lead"})), (4, frozenset({"lead", "pad"})), (8, ALL), (8, ALL), (2, SOFT))),
]


# ---------------------------------------------------------------- composing

def chord(style: Style, degree: int, octave: int = 0) -> list[float]:
    """The chord on ``degree`` of the style's scale, with its seventh for the softer styles."""
    scale = MINOR if style.minor else MAJOR
    steps = [degree - 1, degree + 1, degree + 3] + ([degree + 5] if style.mood in ("lofi", "chill") else [])
    return [hz(style.key + 12 * octave + scale[s % 7] + 12 * (s // 7)) for s in steps]


def compose(style: Style) -> tuple[Signal, Signal, float]:
    """The track as dry and reverb-send stems (mono), and its length in seconds."""
    rng = np.random.default_rng(zlib.crc32(style.id.encode()))
    beat = 60 / style.bpm
    step = beat / 4
    bars = sum(n for n, _ in style.sections)
    seconds = bars * 4 * beat + 3.0
    dry, send = np.zeros(int(seconds * SR)), np.zeros(int(seconds * SR))

    def put(into: Signal, at: float, sound: Signal, gain: float) -> None:
        i = int(at * SR)
        n = min(len(sound), len(into) - i)
        if n > 0:
            into[i:i + n] += gain * sound[:n]

    def at_step(bar_start: float, s: int) -> float:
        return bar_start + s * step + (style.swing * step if s % 2 else 0.0)

    kit = {"kick": kick(), "snare": snare(rng), "clap": clap(rng), "hat": hat(rng), "open": hat(rng, True), "shaker": shaker(rng)}
    bar = 0
    for count, parts in style.sections:
        for _ in range(count):
            start = bar * 4 * beat
            degree = style.progression[bar % len(style.progression)]
            notes = chord(style, degree)
            if "pad" in parts:
                put(send, start, pad([f / 2 for f in notes], 4 * beat + 0.4, 1400 if style.mood == "cinematic" else 2200), 0.5)
            if "lead" in parts and style.lead != "pad":
                for k, s in enumerate(style.rhythm):
                    length = step * 3
                    tones = [notes[k % len(notes)]] if style.arpeggio else notes
                    for f in tones:
                        sound = keys(f, length * 2, 0.8) if style.lead == "keys" else pluck(f * (2 if style.arpeggio else 1), length)
                        put(dry, at_step(start, s), sound, 0.22 if style.arpeggio else 0.13)
                        put(send, at_step(start, s), sound, 0.08)
            elif "lead" in parts:
                put(send, start, pad(notes, 4 * beat + 0.4, 3000), 0.35)
            if "bass" in parts:
                root = chord(style, degree, -2)[0]
                hits = (0, 8) if style.mood in ("cinematic", "chill") else (0, 6, 8, 14) if style.mood == "upbeat" else (0, 8, 10)
                for s in hits:
                    put(dry, at_step(start, s), bass(root, step * 5, "triangle" if style.mood == "funny" else "sine"), 0.5)
            if "drums" in parts:
                for s in range(16):
                    t = at_step(start, s)
                    if style.kick[s] == "x":
                        put(dry, t, kit["kick"], 0.9)
                    if style.snare[s] == "x":
                        put(dry, t, kit["clap" if style.clap_on_snare else "snare"], 0.45)
                        put(send, t, kit["snare"], 0.1)
                    if style.hats[s] == "x":
                        put(dry, t, kit["open"] if s == 14 and style.mood == "upbeat" else kit["hat"], 0.5 if s % 4 else 0.7)
                if style.toms and bar % 2 == 1:
                    for s, f in ((8, 110), (12, 80), (14, 65)):
                        put(dry, at_step(start, s), tom(f), 0.6)
                if style.mood == "funny":
                    for s in (2, 6, 10, 14):
                        put(dry, at_step(start, s), kit["shaker"], 0.6)
            bar += 1
    if style.vinyl:
        dry += crackle(rng, seconds)
    return dry, send, seconds


def reverb(x: Signal, rng: np.random.Generator, seconds: float = 2.2) -> Signal:
    ir = noise(seconds, rng) * decay(seconds, 5.0 / seconds)
    return fftconvolve(x, lowpass(ir, 5000))[: len(x)] * 0.25


def master(style: Style, dry: Signal, send: Signal) -> Signal:
    """Stereo, with the room on its own bus, a soft limit and a fade out; at a bed's level."""
    rng = np.random.default_rng(7)
    wet = reverb(send, rng)
    left = dry + send + wet
    # A few milliseconds between the sides widen the room and pads without moving the drums.
    shift = int(0.012 * SR)
    right = dry + np.concatenate([np.zeros(shift), (send + wet)[:-shift]])
    stereo = highpass(np.stack([left, right]), 30, 2)
    rms = np.sqrt(np.mean(stereo ** 2)) or 1.0
    stereo *= 10 ** (TARGET_RMS_DB / 20) / rms
    stereo = np.tanh(stereo * 1.2) / 1.2
    stereo *= min(1.0, PEAK / (np.abs(stereo).max() or 1.0))
    fade = int(2.5 * SR)
    stereo[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    return stereo


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for style in STYLES:
        dry, send, seconds = compose(style)
        stereo = master(style, dry, send)
        file = f"{style.id}.m4a"
        with tempfile.TemporaryDirectory() as work:
            wav = Path(work) / "track.wav"
            wavfile.write(wav, SR, (stereo.T * 32767).astype(np.int16))
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "aac", "-b:a", "192k",
                            str(OUT / file)], check=True)
        manifest[style.id] = {"file": file, "name": style.name, "mood": style.mood, "tags": list(style.tags), "bpm": style.bpm,
                              "seconds": round(seconds, 2), "licence": LICENCE}
        print(f"{style.id}: {seconds:.0f} s")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
