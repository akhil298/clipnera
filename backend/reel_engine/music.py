"""Music written to the cuts, and the beds and on-demand sounds the asset loop can make.

The score follows the edit's own structure: a muffled build under the hook, a snare roll under a
montage, the drop on the first step (or the reveal), a fill and crash at every section change,
half-time under money shots, a tape-stop into the payoff, and the bed pumping under each kick.
Everything is synthesised (motion.synth), so it is Clipnera's own and nothing for Content ID to match.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from motion.synth import (
    SR, bandpass, bass, boom, chime, clap, decay, hat, highpass, hz, kick, lowpass, noise, osc, pad, pluck, punch,
    reverse_cymbal, riser, shaker, snare, sparkle, sub_drop, swell, tape_stop, thud, tom,
)

BPM = 112
MAJOR = (0, 2, 4, 5, 7, 9, 11)
B = 60 / BPM
S16 = B / 4
PROGRESSION = (1, 5, 6, 4)
TARGET_RMS_DB = -14.0
MOOD_KEYS = {"upbeat": -4, "chill": -9, "cinematic": -12, "dramatic": -10, "corporate": -5, "lofi": -9, "inspiring": -9, "funny": -2}


@dataclass
class Structure:
    """The edit's shape in output seconds, as the score needs it."""

    duration: float
    hook_end: float = 0.0
    roll: tuple[float, float] | None = None
    sections: list[float] = field(default_factory=list)
    payoff: float | None = None
    cta: float | None = None
    money: list[tuple[float, float]] = field(default_factory=list)
    foley: list[tuple[float, float, str]] = field(default_factory=list)
    mood: str = "upbeat"


def _reverb(x: np.ndarray, rng: np.random.Generator, seconds: float = 2.0) -> np.ndarray:
    from scipy.signal import fftconvolve

    ir = noise(seconds, rng) * decay(seconds, 5.0 / seconds)
    return fftconvolve(x, lowpass(ir, 5000))[: len(x)] * 0.25


def foley(kind: str, seconds: float, rng: np.random.Generator) -> np.ndarray:
    """A sound the picture calls for, made on demand: sizzle, chop, pour, sparkle, stamp, pop, ding."""
    seconds = max(0.08, seconds)
    n = int(seconds * SR)
    if kind == "sizzle":
        hiss = bandpass(noise(seconds, rng), 2500, 9000) * (0.6 + 0.4 * rng.random(n) ** 8)
        crackles = lowpass((rng.random(n) > 0.9993) * rng.uniform(-1, 1, n), 6000)
        return (0.12 * hiss + 0.5 * crackles) * swell(seconds, 0.3)
    if kind == "chop":
        return bandpass(noise(0.08, rng), 300, 3000) * decay(0.08, 45) + osc(170, 0.08) * decay(0.08, 60) * 0.6
    if kind == "pour":
        body = bandpass(noise(seconds, rng, "pink"), 300, 2500) * (0.7 + 0.3 * np.sin(2 * np.pi * 7 * np.arange(n) / SR))
        return body * swell(seconds, 0.2) * 0.5
    if kind == "sparkle":
        return sparkle(rng, min(1.6, seconds), 14)
    if kind == "stamp":
        body, hit = thud(rng, "heavy"), punch(rng, "tight", "low")
        return body + 0.5 * np.pad(hit, (0, max(0, len(body) - len(hit))))[: len(body)]
    if kind == "pop":
        return osc(np.linspace(900, 300, int(0.09 * SR)), 0.09) * decay(0.09, 35)
    if kind == "ding":
        return chime(rng, 15)
    raise KeyError(kind)


FOLEY = ("sizzle", "chop", "pour", "sparkle", "stamp", "pop", "ding")


def _chord(key: int, degree: int, lift: int = 0, octave: int = 0) -> list[float]:
    steps = [degree - 1, degree + 1, degree + 3]
    return [hz(key + lift + 12 * octave + MAJOR[s % 7] + 12 * (s // 7)) for s in steps]


def compose(s: Structure, out: Path) -> Path:
    rng = np.random.default_rng(BPM)
    key = MOOD_KEYS.get(s.mood, -4)
    n = int((s.duration + 3) * SR)
    drums, music, send, fx = (np.zeros(n) for _ in range(4))

    def put(into: np.ndarray, at: float, sound: np.ndarray, gain: float) -> None:
        i = int(round(at * SR))
        if i < 0:
            sound, i = sound[-i:], 0
        k = min(len(sound), n - i)
        if k > 0:
            into[i:i + k] += gain * sound[:k]

    k_kick, k_snare, k_clap, k_hat, k_open, k_shaker = kick(), snare(rng), clap(rng), hat(rng), hat(rng, True), shaker(rng)
    first = s.sections[0] if s.sections else (s.roll[1] if s.roll else s.hook_end)
    payoff = s.payoff if s.payoff and s.payoff > first + 2 * B else None
    groove_end = (payoff - B) if payoff else s.duration

    def half(t: float) -> bool:
        return any(a - 1e-3 <= t < b - 1e-3 for a, b in s.money)

    def lift(t: float) -> int:
        return 2 if payoff and t >= payoff else 1 if len(s.sections) > 2 and t >= s.sections[len(s.sections) // 2] else 0

    # hook: muffled pad opening up, a lone kick, reverse cymbal into what follows
    for bar in range(int(np.ceil(max(first, B) / (4 * B)))):
        t = bar * 4 * B
        put(send, t, pad([f / 2 for f in _chord(key, PROGRESSION[bar % 4])], min(4 * B, max(B, first - t)) + 0.3, 700 + 900 * bar), 0.35)
    put(fx, 0.0, boom(rng, 45, "long", "soft"), 0.3)
    for beat in range(0, int(first / B), 2):
        put(drums, beat * B, lowpass(k_kick, 400), 0.55)
    if first > 2 * B:
        put(fx, first - 2 * B, reverse_cymbal(rng, 2 * B), 0.35)
    # montage: 16th snare roll climbing into an eighth of silence
    if s.roll:
        a, b = s.roll[0], s.roll[1] - B / 2
        t, i = a, 0
        while t < b - 1e-3:
            put(drums, t, k_snare, 0.3 + 0.6 * (t - a) / max(0.1, b - a))
            if i % 2 == 0:
                put(drums, t, k_kick, 0.9)
            t += S16
            i += 1
        put(fx, a, riser(rng, max(0.2, b - a), "both"), 0.4)
        put(send, a, pad([f / 2 for f in _chord(key, 5)], b - a + 0.1, 1200), 0.6)
        for f, back in ((196, 4), (147, 3), (110, 2)):
            put(drums, b - back * S16, tom(f), 0.5)

    def groove(start: float, end: float) -> None:
        t = start
        while t < end - 1e-3:
            beat = int(round(t / B))
            degree = PROGRESSION[(beat // 4) % 4]
            notes = _chord(key, degree, lift(t))
            root = _chord(key, degree, lift(t), -2)[0]
            if half(t):
                if beat % 4 == 0:
                    put(drums, t, k_kick, 0.9)
                    put(music, t, bass(root, 4 * B, "sine"), 0.55)
                    put(send, t, pad([f / 2 for f in notes], 4 * B + 0.3, 900), 0.55)
                if beat % 4 == 2:
                    put(drums, t, k_clap, 0.5)
            else:
                put(drums, t, k_kick, 0.9)
                if beat % 2 == 1:
                    put(drums, t, k_clap, 0.45)
                    put(send, t, k_snare, 0.08)
                put(drums, t + B / 2, k_open if beat % 4 == 3 else k_hat, 0.45)
                for q in (1, 3):
                    put(drums, t + q * S16, k_shaker, 0.5)
                put(music, t + B / 2, bass(root, B / 2 - 0.02, "saw"), 0.32)
                for q in range(4):
                    f = notes[(beat * 4 + q) % 3] * (2 if q % 2 else 1)
                    put(music, t + q * S16, pluck(f, S16 * 2.5), 0.16)
                    put(send, t + q * S16, pluck(f, S16 * 2.5), 0.05)
                if beat % 4 == 0:
                    put(send, t, pad([f / 2 for f in notes], 4 * B + 0.3, 2400), 0.35)
            t += B

    groove(first, groove_end)
    if payoff:
        groove(payoff, s.duration)
        put(music, payoff - B, tape_stop(rng, 0.75 * B), 0.35)
        put(fx, payoff, boom(rng, 40, "long", "hard"), 0.55)
    crash = highpass(noise(2.2, rng), 4500) * decay(2.2, 2.0) * 0.5
    for t in s.sections[1:]:
        for q in range(4):
            put(drums, t - B + q * S16, k_snare, 0.3 + 0.12 * q)
        put(fx, t - B, riser(rng, B, "noise"), 0.25)
    for t in [first, *s.sections[1:], *([payoff] if payoff else [])]:
        put(send, t, crash, 0.55)
        put(fx, t, sub_drop(rng, 0.9, 90), 0.6)
        put(fx, t, punch(rng, "roomy", "low"), 0.4)
    for a, b in s.money:
        put(fx, b - 2 * B, riser(rng, 2 * B, "tonal"), 0.2)
    for a, b, kind in s.foley:
        if kind == "chop":
            t = a
            while t < b - 0.05:
                put(fx, t, foley("chop", 0.08, rng), 0.35)
                t += B / 2
        elif kind in FOLEY:
            put(fx, a + (0.2 if kind == "sparkle" else 0.0), foley(kind, b - a, rng), 1.0 if kind == "sizzle" else 0.35)
    if s.cta:
        for q in range(8):
            put(send, s.cta + q * B, pluck(_chord(key, 1, 2, 1)[q % 3], B), 0.08)
    # level automation: the hook sits back, the roll climbs, the drops hit hardest
    marks = [(0.0, -4), (max(0.01, first - 0.01), -3)]
    if s.roll:
        marks += [(s.roll[0], -6), (s.roll[1] - 0.01, -2)]
    marks += [(first, 3), (groove_end, 2)]
    if payoff:
        marks += [(payoff, 5)]
    marks += [(s.duration + 3, 1)]
    marks.sort()
    curve = 10 ** (np.interp(np.arange(n) / SR, [m[0] for m in marks], [m[1] for m in marks]) / 20)
    pump = np.ones(n)
    env = 1 - 0.55 * np.exp(-np.arange(int(B * SR)) / (0.07 * SR))
    t = first
    while t < s.duration:
        if not half(t) and not (payoff and payoff - B <= t < payoff):
            i = int(t * SR)
            pump[i:i + len(env)] = np.minimum(pump[i:i + len(env)], env[: n - i])
        t += B
    bed = (music + send + _reverb(send, rng)) * pump
    shift = int(0.012 * SR)
    left = (drums + bed + fx) * curve
    right = (drums + np.concatenate([np.zeros(shift), bed[:-shift]]) + fx) * curve
    stereo = highpass(np.stack([left, right]), 30, 2)[:, : int(s.duration * SR)]
    rms = np.sqrt(np.mean(stereo ** 2)) or 1.0
    stereo *= 10 ** (TARGET_RMS_DB / 20) / rms
    stereo = np.tanh(stereo * 1.3) / 1.3
    stereo *= min(1.0, 10 ** (-1 / 20) / (np.abs(stereo).max() or 1.0))
    fade = min(int(0.6 * SR), stereo.shape[1])
    stereo[:, stereo.shape[1] - fade:] *= np.linspace(1, 0, fade) ** 2
    wavfile.write(out, SR, (stereo.T * 32767).astype(np.int16))
    return out


def write_foley(kind: str, out: Path, seconds: float = 1.2) -> Path:
    rng = np.random.default_rng(zlib.crc32(kind.encode()))
    signal = foley(kind, seconds, rng)
    signal = signal / (np.abs(signal).max() or 1.0) * 10 ** (-1 / 20)
    wavfile.write(out, SR, (signal * 32767).astype(np.int16))
    return out
