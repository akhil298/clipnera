"""Synthesise Clipnera's own sound-effect pack into ``static/motion/sfx/synth``.

Every sound here is made from oscillators, filtered noise and envelopes in this
file, so Clipnera owns it outright: no licence to track, nothing for Content ID
to match. Each recipe is rendered in a few variants (length, brightness, pitch,
direction) with a fixed seed, so a rebuild writes the same files.

The manifest uses the same fields as the curated pack's (``file``, ``seconds``,
``peak``, ``source``, ``licence``) plus ``category`` and ``tags``, so the two
can be read the same way. ``peak`` is where the loudest sample falls, which is
what gets lined up with a visual event; ``loudness_db`` is the average level.

    cd backend && venv/bin/python scripts/build_synth_sfx.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motion.synth import *  # noqa: E402,F403  (every recipe the pack below renders)
from motion.synth import SR, Signal  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "static" / "motion" / "sfx" / "synth"
PEAK_DB = -1.0
LICENCE = "Clipnera original, synthesised in code"



# ---------------------------------------------------------------- the pack

@dataclass
class Sound:
    name: str
    category: str
    tags: list[str]
    recipe: Callable[..., Signal]
    params: dict[str, object] = field(default_factory=dict)


def _variants(prefix: str, category: str, tags: list[str], recipe: Callable[..., Signal], **grid: list[object]) -> list[Sound]:
    keys = list(grid)
    sounds = []
    for values in product(*(grid[k] for k in keys)):
        params = dict(zip(keys, values, strict=True))
        suffix = "_".join(_label(v) for v in values)
        sounds.append(Sound(f"{prefix}_{suffix}" if suffix else prefix, category, tags, recipe, params))
    return sounds


def _label(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}".replace(".", "p")
    if isinstance(value, tuple):
        return "-".join(_label(v) for v in value)
    return str(value)


def pack() -> list[Sound]:
    v = _variants
    return [
        *v("whoosh", "transition", ["whoosh", "movement", "cut"], whoosh,
           seconds=[0.4, 0.7, 1.0, 1.4], tone=["dark", "mid", "bright"], direction=["up", "down"]),
        *v("swoosh", "transition", ["swoosh", "fast", "swipe"], swoosh, seconds=[0.18, 0.25, 0.35], tone=["mid", "bright", "air"]),
        *v("riser", "build", ["riser", "tension", "build-up"], riser, seconds=[1.0, 2.0, 3.0, 4.0], flavour=["tonal", "noise", "both"]),
        *v("downlifter", "build", ["downlifter", "release", "fall"], downlifter, seconds=[0.8, 1.5, 2.5], flavour=["tonal", "noise"]),
        *v("reverse_cymbal", "build", ["reverse", "cymbal", "swell"], reverse_cymbal, seconds=[0.8, 1.5, 2.5]),
        *v("boom", "impact", ["boom", "impact", "cinematic"], boom, freq=[42.0, 55.0, 70.0], tail=["short", "long"], attack=["soft", "hard"]),
        *v("sub_drop", "impact", ["sub", "drop", "bass"], sub_drop, seconds=[0.6, 1.2, 2.0], start_hz=[90.0, 130.0]),
        *v("punch", "impact", ["punch", "hit"], punch, room_size=["tight", "roomy"], pitch=["low", "mid", "high"]),
        *v("pop", "pop", ["pop", "appear"], pop, freq=[400.0, 600.0, 800.0, 1100.0, 1500.0], length=["short", "long"]),
        *v("bubble", "pop", ["bubble", "appear", "cute"], bubble, freq=[300.0, 450.0, 600.0, 800.0, 1000.0]),
        *v("click", "ui", ["click", "tap"], click, kind=["tone"], freq=[1500.0, 2500.0, 4000.0]),
        *v("click", "ui", ["click", "tap"], click, kind=["noise"], freq=[2000.0, 5000.0]),
        *v("click", "ui", ["click", "wood", "knock"], click, kind=["wood"], freq=[700.0, 1200.0, 1800.0]),
        *v("tick", "counter", ["tick", "count", "clock"], tick, freq=[1800.0, 2600.0, 3400.0], pattern=["single", "ticktock"]),
        *v("chime", "chime", ["chime", "bell", "ding", "reveal"], chime, semitones=[3.0, 5.0, 7.0, 10.0, 12.0, 15.0, 17.0, 19.0]),
        *v("success", "ui", ["success", "correct", "done"], arpeggio, steps=[(0, 4, 7), (0, 7, 12), (0, 4, 7, 12)],
           gap=[0.08, 0.12], wave=["sine"], root=[3.0]),
        *v("error", "ui", ["error", "wrong", "fail"], arpeggio, steps=[(0, -3), (0, -6), (0, -1, -2)], gap=[0.15], wave=["square"], root=[-2.0]),
        *v("notify", "ui", ["notification", "message", "alert"], arpeggio, steps=[(0, 5), (0, 12), (7, 0)], gap=[0.1], wave=["triangle"], root=[10.0]),
        *v("beep", "ui", ["beep", "tone"], beep, freq=[440.0, 880.0, 1000.0, 1760.0], length=["short", "long"]),
        *v("beep", "ui", ["beep", "censor", "bleep"], beep, freq=[1000.0], length=["censor"]),
        *v("glitch", "glitch", ["glitch", "digital", "error"], glitch, seconds=[0.15, 0.25, 0.4, 0.6, 0.9]),
        *v("zap", "glitch", ["zap", "laser", "electric"], zap, start_hz=[1200.0, 2400.0, 4000.0], wave=["square", "saw"]),
        *v("typing", "foley", ["typing", "keyboard"], typing, seconds=[0.8, 1.5, 2.5], style=["laptop", "mechanical"]),
        *v("shutter", "foley", ["camera", "shutter", "photo"], shutter, speed=["fast", "normal", "slow"]),
        *v("coin", "money", ["coin", "reward", "collect"], coin, first=[19.0, 14.0], second=[26.0, 24.0]),
        *v("ka_ching", "money", ["cash", "money", "register", "sale"], ka_ching, variant=[0, 1, 2]),
        *v("sparkle", "magic", ["sparkle", "magic", "shine"], sparkle, seconds=[0.6, 1.0, 1.6], density=[12, 30]),
        *v("heartbeat", "tension", ["heartbeat", "suspense"], heartbeat, bpm=[60.0, 100.0], beats=[2, 4]),
        *v("tape_stop", "transition", ["tape stop", "slow down", "stop"], tape_stop, seconds=[0.5, 0.9, 1.4]),
        *v("scratch", "transition", ["scratch", "record", "stop"], scratch, seconds=[0.25, 0.45, 0.7]),
        *v("boing", "comedy", ["boing", "spring", "funny"], boing, freq=[150.0, 220.0, 330.0, 440.0]),
        *v("slide_whistle", "comedy", ["slide whistle", "funny"], slide_whistle, direction=["up", "down"], seconds=[0.5, 1.0]),
        *v("kick", "drum", ["kick", "drum", "beat"], drum, kind=["kick"], variant=[0, 1, 2]),
        *v("snare", "drum", ["snare", "drum", "hit"], drum, kind=["snare"], variant=[0, 1, 2]),
        *v("clap", "drum", ["clap", "applause"], drum, kind=["clap"], variant=[0, 1, 2]),
        *v("hat", "drum", ["hi-hat", "cymbal"], drum, kind=["hat_closed", "hat_open"], variant=[0, 1]),
        *v("drum_roll", "drum", ["drum roll", "reveal", "suspense"], drum_roll, seconds=[1.5, 3.0]),
        *v("rumble", "ambience", ["rumble", "earthquake", "low"], rumble, seconds=[1.5, 3.0, 5.0]),
        *v("wind", "ambience", ["wind", "air", "gust"], wind, seconds=[1.5, 3.0, 5.0]),
        *v("static", "glitch", ["static", "tv", "noise"], static_burst, seconds=[0.3, 0.8, 1.5]),
        *v("ui_swipe", "ui", ["swipe", "slide", "card"], ui_swipe, seconds=[0.12, 0.2, 0.3, 0.45]),
        *v("toggle", "ui", ["toggle", "switch"], toggle, state=["on", "off"], pitch=[1800.0, 3000.0]),
        *v("thud", "impact", ["thud", "drop", "land"], thud, weight=["light", "medium", "heavy", "body"]),
        *v("page_turn", "foley", ["page", "paper", "flip"], page_turn, seconds=[0.3, 0.5, 0.8]),
        *v("alarm", "alert", ["alarm", "warning"], alarm, kind=["siren", "buzzer", "beeping"]),
        *v("stinger", "music", ["stinger", "reveal", "dramatic"], stinger, chord=[(0, 3, 7), (0, 4, 7), (0, 3, 6), (0, 5, 7)]),
        *v("braam", "music", ["braam", "trailer", "epic"], braam, root=[-17.0, -14.0, -12.0]),
    ]


def finish(x: Signal) -> Signal:
    """DC removed, silence trimmed off the tail, edges faded, peak at PEAK_DB."""
    x = highpass(np.nan_to_num(x), 20, 2)
    level = np.abs(x) / (np.abs(x).max() or 1.0)
    loud = np.nonzero(level > 10 ** (-60 / 20))[0]
    x = x[: loud[-1] + 1] if loud.size else x
    fade_in, fade_out = min(len(x), int(0.001 * SR)), min(len(x), int(0.01 * SR))
    x[:fade_in] *= np.linspace(0, 1, fade_in)
    x[len(x) - fade_out:] *= np.linspace(1, 0, fade_out)
    return x * (10 ** (PEAK_DB / 20) / (np.abs(x).max() or 1.0))


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sounds = pack()
    names = [s.name for s in sounds]
    if len(names) != len(set(names)):
        raise SystemExit(f"duplicate names: {sorted({n for n in names if names.count(n) > 1})}")
    manifest: dict[str, dict[str, object]] = {}
    for index, sound in enumerate(sounds):
        samples = finish(sound.recipe(np.random.default_rng(index), **sound.params))
        target = OUT / f"{sound.name}.wav"
        wavfile.write(target, SR, (samples * 32767).astype(np.int16))
        manifest[sound.name] = {
            "file": target.name,
            "seconds": round(len(samples) / SR, 3),
            "peak": round(int(np.argmax(np.abs(samples))) / SR, 3),
            # Average level (RMS dBFS): peaks are all at PEAK_DB, so this is what a mixer evens out.
            "loudness_db": round(float(20 * np.log10(np.sqrt(np.mean(samples ** 2)) + 1e-12)), 1),
            "source": f"scripts/build_synth_sfx.py {sound.recipe.__name__}({', '.join(f'{k}={_label(v)}' for k, v in sound.params.items())})",
            "licence": LICENCE,
            "category": sound.category,
            "tags": sound.tags,
        }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{len(manifest)} sounds -> {OUT}")


if __name__ == "__main__":
    build()
