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
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, istft, sosfilt, stft

OUT = Path(__file__).resolve().parents[1] / "static" / "motion" / "sfx" / "synth"
SR = 48000
PEAK_DB = -1.0
LICENCE = "Clipnera original, synthesised in code"

Signal = np.ndarray


# ---------------------------------------------------------------- building blocks

def times(seconds: float) -> Signal:
    return np.arange(int(seconds * SR)) / SR


def noise(seconds: float, rng: np.random.Generator, color: str = "white") -> Signal:
    """White, pink (-3 dB/oct) or brown (-6 dB/oct) noise, shaped in the frequency domain."""
    n = int(seconds * SR)
    white = rng.standard_normal(n)
    if color == "white":
        return white
    spectrum = np.fft.rfft(white)
    freqs = np.maximum(np.fft.rfftfreq(n, 1 / SR), 20.0)
    spectrum /= np.sqrt(freqs) if color == "pink" else freqs
    shaped = np.fft.irfft(spectrum, n)
    return shaped / (np.abs(shaped).max() or 1.0)


def _filter(x: Signal, kind: str, freq: float | tuple[float, float], order: int = 4) -> Signal:
    if isinstance(freq, tuple):
        freq = (max(20.0, freq[0]), min(SR / 2 - 100, freq[1]))
    else:
        freq = min(max(20.0, freq), SR / 2 - 100)
    return sosfilt(butter(order, freq, btype=kind, fs=SR, output="sos"), x)


def lowpass(x: Signal, freq: float, order: int = 4) -> Signal:
    return _filter(x, "lowpass", freq, order)


def highpass(x: Signal, freq: float, order: int = 4) -> Signal:
    return _filter(x, "highpass", freq, order)


def bandpass(x: Signal, low: float, high: float, order: int = 2) -> Signal:
    return _filter(x, "bandpass", (low, high), order)


def sweep(x: Signal, start_hz: float, end_hz: float, width_oct: float = 1.0) -> Signal:
    """``x`` through a band that glides from ``start_hz`` to ``end_hz`` (log scale), via the STFT."""
    f, frames, spec = stft(x, SR, nperseg=1024)
    centre = np.geomspace(start_hz, end_hz, spec.shape[1])
    octaves = np.log2(np.maximum(f[:, None], 1.0) / centre[None, :])
    spec *= np.exp(-0.5 * (octaves / width_oct) ** 2)
    return istft(spec, SR, nperseg=1024)[1][: len(x)]


def osc(freq: float | Signal, seconds: float, wave: str = "sine") -> Signal:
    """An oscillator at a fixed or per-sample frequency; square and saw are low-passed against aliasing."""
    n = int(seconds * SR)
    hz = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    phase = 2 * np.pi * np.cumsum(hz) / SR
    if wave == "sine":
        return np.sin(phase)
    if wave == "triangle":
        return 2 / np.pi * np.arcsin(np.sin(phase))
    if wave == "square":
        return lowpass(np.sign(np.sin(phase)), 9000, 2)
    if wave == "saw":
        return lowpass(2 * ((phase / (2 * np.pi)) % 1.0) - 1, 9000, 2)
    raise ValueError(wave)


def glide(start_hz: float, end_hz: float, seconds: float, curve: str = "exp") -> Signal:
    k = np.linspace(0.0, 1.0, int(seconds * SR))
    return start_hz * (end_hz / start_hz) ** k if curve == "exp" else start_hz + (end_hz - start_hz) * k


def decay(seconds: float, rate: float) -> Signal:
    return np.exp(-rate * times(seconds))


def swell(seconds: float, peak_at: float = 0.7) -> Signal:
    """Rises smoothly to 1 at ``peak_at`` of the length, then falls away."""
    k = np.linspace(0.0, 1.0, int(seconds * SR))
    rise = np.sin(np.pi / 2 * np.clip(k / peak_at, 0, 1)) ** 2
    fall = np.cos(np.pi / 2 * np.clip((k - peak_at) / (1 - peak_at), 0, 1)) ** 2
    return np.where(k <= peak_at, rise, fall)


def bell(freq: float, seconds: float, brightness: float = 1.0) -> Signal:
    """A struck-metal tone: inharmonic partials, the higher ones dying first."""
    out = np.zeros(int(seconds * SR))
    for ratio, amp, rate in ((1.0, 1.0, 3.0), (2.76, 0.5, 5.0), (5.40, 0.28, 8.0), (8.93, 0.14, 12.0)):
        if freq * ratio < SR / 2 - 1000:
            out += amp * brightness ** (ratio > 1) * osc(freq * ratio, seconds) * decay(seconds, rate)
    return out * np.minimum(1.0, times(seconds) / 0.002)


def room(x: Signal, rng: np.random.Generator, seconds: float = 0.6, mix: float = 0.25) -> Signal:
    """A small room: convolution with a short burst of decaying noise."""
    ir = noise(seconds, rng) * decay(seconds, 6.0 / seconds)
    wet = np.convolve(x, lowpass(ir, 6000))[: len(x) + int(seconds * SR)]
    wet *= np.abs(x).max() / (np.abs(wet).max() or 1.0)
    dry = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return (1 - mix) * dry + mix * wet


def place(parts: list[tuple[float, Signal]], seconds: float) -> Signal:
    """Mixes each signal in at its start time into a buffer ``seconds`` long."""
    out = np.zeros(int(seconds * SR))
    for at, part in parts:
        i = int(at * SR)
        n = min(len(part), len(out) - i)
        if n > 0:
            out[i: i + n] += part[:n]
    return out


def note(semitones_from_a4: float) -> float:
    return 440.0 * 2 ** (semitones_from_a4 / 12)


# ---------------------------------------------------------------- recipes

BRIGHTNESS = {"dark": (250, 1400), "mid": (500, 3500), "bright": (1200, 8000)}


def whoosh(rng, seconds: float, tone: str, direction: str) -> Signal:
    low, high = BRIGHTNESS[tone]
    start, end = (low, high) if direction == "up" else (high, low)
    return sweep(noise(seconds, rng, "pink"), start, end, 0.9) * swell(seconds, 0.6 if direction == "up" else 0.4)


def swoosh(rng, seconds: float, tone: str) -> Signal:
    low, high = {"mid": (1500, 6000), "bright": (3000, 11000), "air": (5000, 15000)}[tone]
    return sweep(noise(seconds, rng), low, high, 0.7) * swell(seconds, 0.5)


def riser(rng, seconds: float, flavour: str) -> Signal:
    parts = np.zeros(int(seconds * SR))
    if flavour in ("tonal", "both"):
        tone = osc(glide(110, 880, seconds), seconds, "saw") + 0.5 * osc(glide(111.5, 893, seconds), seconds, "saw")
        parts += 0.5 * sweep(tone, 400, 6000, 1.5)
    if flavour in ("noise", "both"):
        parts += sweep(noise(seconds, rng), 600, 12000, 1.0)
    ramp = np.linspace(0, 1, len(parts)) ** 2
    return parts * ramp * np.minimum(1.0, (seconds - times(seconds)) / 0.03)


def downlifter(rng, seconds: float, flavour: str) -> Signal:
    if flavour == "tonal":
        body = osc(glide(900, 70, seconds), seconds, "saw")
        body = sweep(body, 5000, 300, 1.5)
    else:
        body = sweep(noise(seconds, rng), 10000, 400, 1.0)
    return body * (1 - np.linspace(0, 1, len(body))) ** 1.5 * np.minimum(1.0, times(seconds) / 0.01)


def reverse_cymbal(rng, seconds: float) -> Signal:
    shimmer = highpass(noise(seconds, rng), 4000) * np.linspace(0, 1, int(seconds * SR)) ** 3
    return shimmer * np.minimum(1.0, (seconds - times(seconds)) / 0.01)


def boom(rng, freq: float, tail: str, attack: str) -> Signal:
    seconds = 2.2 if tail == "long" else 1.0
    body = osc(glide(freq * 1.6, freq, 0.12).tolist() + [freq] * (int(seconds * SR) - int(0.12 * SR)), seconds)
    body *= decay(seconds, 2.5 if tail == "long" else 5.0)
    hit = lowpass(noise(seconds, rng), 2500 if attack == "soft" else 7000) * decay(seconds, 40.0)
    return room(body + (0.4 if attack == "soft" else 0.8) * hit, rng, 0.8, 0.2)


def sub_drop(rng, seconds: float, start_hz: float) -> Signal:
    return osc(glide(start_hz, 32, seconds), seconds) * decay(seconds, 1.2 / seconds) * np.minimum(1.0, times(seconds) / 0.005)


def punch(rng, room_size: str, pitch: str) -> Signal:
    freq = {"low": 70, "mid": 110, "high": 170}[pitch]
    seconds = 0.5
    body = osc(glide(freq * 2.5, freq, seconds), seconds) * decay(seconds, 12.0)
    crack = bandpass(noise(seconds, rng), 800, 5000) * decay(seconds, 60.0)
    hit = body + 0.7 * crack
    return room(hit, rng, 0.9, 0.35) if room_size == "roomy" else hit


def pop(rng, freq: float, length: str) -> Signal:
    seconds = 0.12 if length == "short" else 0.25
    return osc(freq + 1.5 * freq * decay(seconds, 45.0), seconds) * decay(seconds, 30.0 if length == "short" else 16.0)


def bubble(rng, freq: float) -> Signal:
    seconds = 0.18
    return osc(glide(freq, freq * 2.2, seconds), seconds) * swell(seconds, 0.25)


def click(rng, kind: str, freq: float) -> Signal:
    seconds = 0.06
    if kind == "tone":
        return osc(freq, seconds) * decay(seconds, 140.0)
    if kind == "noise":
        return highpass(noise(seconds, rng), freq) * decay(seconds, 200.0)
    return bandpass(noise(seconds, rng), freq * 0.8, freq * 1.25) * decay(seconds, 90.0)  # wood


def tick(rng, freq: float, pattern: str) -> Signal:
    one = bandpass(noise(0.05, rng), freq * 0.9, freq * 1.1) * decay(0.05, 120.0) + 0.3 * osc(freq, 0.05) * decay(0.05, 150.0)
    if pattern == "single":
        return one
    tock = bandpass(noise(0.05, rng), freq * 0.6, freq * 0.75) * decay(0.05, 120.0)
    return place([(0.0, one), (0.28, tock)], 0.4)


def chime(rng, semitones: float) -> Signal:
    return room(bell(note(semitones), 1.6), rng, 1.0, 0.2)


def arpeggio(rng, steps: tuple[float, ...], gap: float, wave: str, root: float) -> Signal:
    tones = [(i * gap, osc(note(root + s), 0.35, wave) * decay(0.35, 9.0) * np.minimum(1.0, times(0.35) / 0.004))
             for i, s in enumerate(steps)]
    return room(place(tones, gap * len(steps) + 0.4), rng, 0.5, 0.18)


def beep(rng, freq: float, length: str) -> Signal:
    seconds = {"short": 0.12, "long": 0.45, "censor": 0.8}[length]
    edge = np.minimum(1.0, np.minimum(times(seconds), seconds - times(seconds)) / 0.006)
    return osc(freq, seconds, "sine" if length != "censor" else "square") * edge


def glitch(rng, seconds: float) -> Signal:
    """Stuttered sample-and-hold noise and crushed tones, re-chosen every few milliseconds."""
    out = np.zeros(int(seconds * SR))
    i = 0
    while i < len(out):
        n = int(rng.uniform(0.008, 0.05) * SR)
        kind = rng.integers(3)
        if kind == 0:
            hold = int(rng.integers(8, 120))
            seg = np.repeat(rng.uniform(-1, 1, n // hold + 1), hold)[:n]
        elif kind == 1:
            seg = np.sign(np.sin(2 * np.pi * rng.uniform(200, 3000) * np.arange(n) / SR))
        else:
            seg = np.zeros(n)
        out[i: i + n] = seg[: len(out) - i] * rng.uniform(0.4, 1.0)
        i += n
    return lowpass(out, 11000)


def zap(rng, start_hz: float, wave: str) -> Signal:
    seconds = 0.35
    return osc(glide(start_hz, start_hz / 8, seconds), seconds, wave) * decay(seconds, 9.0)


def typing(rng, seconds: float, style: str) -> Signal:
    keys, at = [], 0.0
    while at < seconds - 0.05:
        freq = rng.uniform(1800, 3200) if style == "laptop" else rng.uniform(900, 1800)
        key = bandpass(noise(0.04, rng), freq * 0.7, freq * 1.4) * decay(0.04, 160.0) * rng.uniform(0.5, 1.0)
        keys.append((at, key))
        at += rng.uniform(0.06, 0.16)
    return room(place(keys, seconds), rng, 0.25, 0.15)


def shutter(rng, speed: str) -> Signal:
    gap = {"fast": 0.05, "normal": 0.09, "slow": 0.16}[speed]
    snap = lambda f: bandpass(noise(0.05, rng), f, f * 3) * decay(0.05, 110.0)  # noqa: E731
    return room(place([(0.0, snap(1500)), (gap, 0.8 * snap(900))], gap + 0.12), rng, 0.3, 0.12)


def coin(rng, first: float, second: float) -> Signal:
    a = osc(note(first), 0.07, "triangle")
    b = osc(note(second), 0.45, "triangle") * decay(0.45, 7.0)
    return place([(0.0, a), (0.07, b)], 0.55)


def ka_ching(rng, variant: int) -> Signal:
    rattle = bandpass(noise(0.35, rng), 2500, 7000) * decay(0.35, 12.0) * 0.5
    ring = bell(note(15 + variant * 2), 1.2, 1.2) + 0.6 * bell(note(22 + variant * 2), 1.2, 1.2)
    return room(place([(0.0, rattle), (0.12, ring)], 1.4), rng, 0.6, 0.2)


def sparkle(rng, seconds: float, density: int) -> Signal:
    grains = [(rng.uniform(0, seconds - 0.25), osc(rng.uniform(2500, 7000), 0.25) * decay(0.25, rng.uniform(15, 30)) * rng.uniform(0.3, 1))
              for _ in range(int(density * seconds))]
    wet = room(place(grains, seconds), rng, 0.8, 0.3)
    shape = swell(seconds + 0.8, 0.35)
    n = min(len(wet), len(shape))
    return wet[:n] * shape[:n]


def heartbeat(rng, bpm: float, beats: int) -> Signal:
    thump = lambda f: lowpass(osc(glide(f * 1.5, f, 0.15), 0.15) * decay(0.15, 25.0), 300)  # noqa: E731
    period = 60.0 / bpm
    return place([(i * period + d, thump(f)) for i in range(beats) for d, f in ((0.0, 55), (0.24, 48))], beats * period + 0.2)


def tape_stop(rng, seconds: float) -> Signal:
    tone = osc(glide(330, 30, seconds, "lin"), seconds, "saw") + 0.6 * osc(glide(165, 15, seconds, "lin"), seconds, "triangle")
    return lowpass(tone, 3000) * (1 - np.linspace(0, 1, int(seconds * SR))) ** 0.5


def scratch(rng, seconds: float) -> Signal:
    wobble = 900 + 700 * np.sin(2 * np.pi * rng.uniform(5, 9) * times(seconds))
    body = osc(wobble, seconds, "saw") * 0.4 + bandpass(noise(seconds, rng), 600, 3000)
    return body * swell(seconds, 0.3)


def boing(rng, freq: float) -> Signal:
    seconds = 0.7
    pitch = freq * (1 + 0.25 * np.sin(2 * np.pi * 14 * times(seconds)) * decay(seconds, 5.0)) * glide(1.0, 1.6, seconds)
    return osc(pitch, seconds, "triangle") * decay(seconds, 5.0)


def slide_whistle(rng, direction: str, seconds: float) -> Signal:
    start, end = (500, 1800) if direction == "up" else (1800, 500)
    vibrato = 1 + 0.01 * np.sin(2 * np.pi * 6 * times(seconds))
    return osc(glide(start, end, seconds) * vibrato, seconds) * swell(seconds, 0.5)


def drum(rng, kind: str, variant: int) -> Signal:
    if kind == "kick":
        seconds = 0.5
        return osc(glide(150 + 30 * variant, 45, 0.08).tolist() + [45] * (int(seconds * SR) - int(0.08 * SR)), seconds) * decay(seconds, 9.0 - variant)
    if kind == "snare":
        seconds = 0.35
        return 0.6 * osc(190 + 20 * variant, seconds, "triangle") * decay(seconds, 25.0) + bandpass(noise(seconds, rng), 1500, 9000) * decay(seconds, 14.0 + 4 * variant)
    if kind == "clap":
        bursts = [(i * 0.011, bandpass(noise(0.2, rng), 900, 4000) * decay(0.2, 30.0 + 10 * variant)) for i in range(3 + variant)]
        return room(place(bursts, 0.4), rng, 0.4, 0.25)
    seconds = 0.08 if kind == "hat_closed" else 0.5
    return highpass(noise(seconds, rng), 7000 + 1000 * variant) * decay(seconds, 60.0 if kind == "hat_closed" else 7.0)


def drum_roll(rng, seconds: float) -> Signal:
    hits, at, gap = [], 0.0, 0.07
    while at < seconds:
        hits.append((at, drum(rng, "snare", 1) * (0.4 + 0.6 * at / seconds)))
        at += gap
        gap = max(0.035, gap * 0.97)
    return place(hits + [(seconds, drum(rng, "kick", 1) + drum(rng, "hat_open", 0))], seconds + 0.6)


def rumble(rng, seconds: float) -> Signal:
    return lowpass(noise(seconds, rng, "brown"), 140) * swell(seconds, 0.3)


def wind(rng, seconds: float) -> Signal:
    gust = 0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(0.3, 0.7) * times(seconds) + rng.uniform(0, 6))
    return sweep(noise(seconds, rng, "pink"), 300, 1200, 1.2) * gust * swell(seconds, 0.5)


def static_burst(rng, seconds: float) -> Signal:
    crackle = noise(seconds, rng) * (rng.random(int(seconds * SR)) < 0.3)
    return highpass(crackle, 800) * np.minimum(1.0, np.minimum(times(seconds), seconds - times(seconds)) / 0.01)


def ui_swipe(rng, seconds: float) -> Signal:
    return sweep(noise(seconds, rng), 2000, 6000, 0.6) * swell(seconds, 0.3) * 0.7


def toggle(rng, state: str, pitch: float) -> Signal:
    a = click(rng, "tone", pitch)
    b = click(rng, "tone", pitch * (1.5 if state == "on" else 0.67))
    return place([(0.0, a), (0.05, b)], 0.14)


def thud(rng, weight: str) -> Signal:
    freq, seconds = {"light": (120, 0.25), "medium": (80, 0.4), "heavy": (55, 0.7), "body": (65, 0.5)}[weight]
    body = osc(glide(freq * 1.8, freq, 0.05).tolist() + [freq] * (int(seconds * SR) - int(0.05 * SR)), seconds) * decay(seconds, 10.0)
    return body + lowpass(noise(seconds, rng), 900) * decay(seconds, 40.0) * 0.6


def page_turn(rng, seconds: float) -> Signal:
    flutter = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(25, 40) * times(seconds))
    return sweep(noise(seconds, rng), 1500, 5000, 1.0) * flutter * swell(seconds, 0.6)


def alarm(rng, kind: str) -> Signal:
    seconds = 1.2
    if kind == "siren":
        pitch = 700 + 350 * np.sin(2 * np.pi * 1.6 * times(seconds))
    elif kind == "buzzer":
        return osc(180, 0.6, "square") * np.minimum(1.0, np.minimum(times(0.6), 0.6 - times(0.6)) / 0.01) * 0.6
    else:  # beeping
        pitch = np.full(int(seconds * SR), 1000.0)
    gate = (np.sin(2 * np.pi * 4 * times(seconds)) > 0) if kind == "beeping" else 1.0
    return osc(pitch, seconds, "square") * gate * 0.6


def stinger(rng, chord: tuple[float, ...]) -> Signal:
    seconds = 2.0
    pad = sum(osc(note(s - 12), seconds, "saw") for s in chord) / len(chord)
    pad = lowpass(pad, 2500) * decay(seconds, 1.6)
    return room(place([(0.0, pad), (0.0, boom(rng, 55, "short", "hard"))], seconds), rng, 1.0, 0.25)


def braam(rng, root: float) -> Signal:
    seconds = 2.5
    cluster = sum(osc(note(root + s) * d, seconds, "saw") for s, d in ((0, 1.0), (7, 1.003), (12, 0.997), (-12, 1.0)))
    opening = sweep(cluster, 200, 1500, 1.4) * np.minimum(1.0, times(seconds) / 0.03) * decay(seconds, 1.2)
    return room(opening, rng, 1.2, 0.3)


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
