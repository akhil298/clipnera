"""Clipnera's sound synthesis: oscillators, filtered noise, envelopes, sound-effect recipes and instruments.

Everything Clipnera synthesises comes from here, so Clipnera owns it outright: no licence to track,
nothing for Content ID to match. The sound-effect pack (scripts/build_synth_sfx.py), the music beds
(scripts/build_synth_music.py) and the reel engine's scores and on-demand sounds all build on it.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, istft, sosfilt, stft

SR = 48000

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


def hz(semitones_from_a4: float) -> float:
    return 440.0 * 2 ** (semitones_from_a4 / 12)


# ---------------------------------------------------------------- instruments (mono, one note each)

def kick(punch: float = 1.0) -> Signal:
    body = osc(glide(150 * punch, 45, 0.35), 0.35) * decay(0.35, 11)
    click = highpass(noise(0.01, np.random.default_rng(1)), 2000) * 0.3
    return body + np.pad(click, (0, len(body) - len(click)))


def snare(rng: np.random.Generator) -> Signal:
    rattle = bandpass(noise(0.22, rng), 1500, 7000) * decay(0.22, 16)
    tone = osc(185, 0.22) * decay(0.22, 28)
    return 0.8 * rattle + 0.5 * tone


def clap(rng: np.random.Generator) -> Signal:
    out = np.zeros(int(0.25 * SR))
    for at in (0.0, 0.012, 0.024):
        burst = bandpass(noise(0.2, rng), 900, 5000) * decay(0.2, 30 if at < 0.02 else 14)
        i = int(at * SR)
        out[i:i + len(burst)] += burst[: len(out) - i]
    return out * 0.6


def hat(rng: np.random.Generator, open_: bool = False) -> Signal:
    length = 0.25 if open_ else 0.05
    return highpass(noise(length, rng), 7000) * decay(length, 12 if open_ else 70) * 0.35


def shaker(rng: np.random.Generator) -> Signal:
    return bandpass(noise(0.09, rng), 5000, 11000) * swell(0.09, 0.3) * 0.25


def tom(freq: float) -> Signal:
    return osc(glide(freq * 1.6, freq, 0.5), 0.5) * decay(0.5, 7)


def keys(freq: float, seconds: float, brightness: float = 1.0) -> Signal:
    """An electric piano: a few harmonics, the upper ones fading first, a soft tremolo."""
    t = times(seconds)
    tone = osc(freq, seconds) + 0.35 * brightness * osc(2 * freq, seconds) * decay(seconds, 4) \
        + 0.12 * brightness * osc(3 * freq, seconds) * decay(seconds, 7)
    attack = np.minimum(1.0, t / 0.004)
    return tone * attack * decay(seconds, 2.2) * (1 + 0.06 * np.sin(2 * np.pi * 4.5 * t))


def pluck(freq: float, seconds: float) -> Signal:
    raw = osc(freq, seconds, "saw") + 0.5 * osc(freq * 1.005, seconds, "saw")
    return lowpass(raw, min(6000, freq * 6)) * decay(seconds, 9) * np.minimum(1.0, times(seconds) / 0.002) * 0.6


def pad(freqs: list[float], seconds: float, cutoff: float = 1800) -> Signal:
    """Detuned saws, filtered soft, swelling in and out over the chord."""
    out = np.zeros(int(seconds * SR))
    for f in freqs:
        for cents in (-8, 0, 7):
            out += osc(f * 2 ** (cents / 1200), seconds, "saw")
    return lowpass(out / (3 * len(freqs)), cutoff, 2) * swell(seconds, 0.35)


def bass(freq: float, seconds: float, wave: str = "sine") -> Signal:
    tone = osc(freq, seconds, wave) + 0.4 * osc(freq / 2, seconds)
    env = np.minimum(1.0, times(seconds) / 0.006) * np.exp(-1.2 * times(seconds))
    release = np.minimum(1.0, (seconds - times(seconds)) / 0.03)
    return lowpass(tone, 900) * env * release


def crackle(rng: np.random.Generator, seconds: float) -> Signal:
    """Vinyl: faint hiss and the odd pop."""
    hiss = lowpass(noise(seconds, rng, "pink"), 4000) * 0.015
    pops = (rng.random(int(seconds * SR)) > 0.99985) * rng.uniform(-0.25, 0.25, int(seconds * SR))
    return hiss + lowpass(pops, 3000)
