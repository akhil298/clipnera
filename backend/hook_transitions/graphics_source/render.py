"""Render the hook-bridge motion graphics and their sound effects.

    cd backend && venv/bin/python -m hook_transitions.graphics_source.render

Every graphic is drawn here from code (numpy + Pillow), so the library is
original work with no licence to track. Each is written to
``static/motion/hook_graphics/<id>.mp4`` as a *packed-alpha* H.264 video: colour on
the left half, its alpha matte (as grey) on the right. Any FFmpeg build can
composite that (crop both halves, ``alphamerge``), unlike alpha codecs, and the
files stay small. Each graphic's sound effect is synthesised beside it as
``sfx/<id>.wav``, and ``manifest.json`` lists them for ``hook_transitions.graphics``.
"""

from __future__ import annotations

import json
import math
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = (
    Path(__file__).resolve().parent.parent.parent / "static" / "motion" / "hook_graphics"
)
W, H = 1080, 1920
FPS = 30
SECONDS = 1.0
FRAMES = int(FPS * SECONDS)
SR = 48000
# Soft graphics are drawn at half size and scaled up: indistinguishable once blurred, 4x faster.
LW, LH = W // 2, H // 2

Frame = tuple[np.ndarray, np.ndarray]  # rgb float32 HxWx3 in 0..1, alpha float32 HxW in 0..1


def ease_out(u: float) -> float:
    return 1 - (1 - min(max(u, 0.0), 1.0)) ** 3


def ease_in_out(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def bell(t: float, peak: float = 0.35, width: float = 0.3) -> float:
    """0 -> 1 at ``peak`` -> 0, smooth on both sides."""
    if t <= peak:
        return math.sin(min(1.0, t / max(peak, 1e-6)) * math.pi / 2) ** 2
    return math.cos(min(1.0, (t - peak) / max(1 - peak, 1e-6)) * math.pi / 2) ** 2


def grid(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return xs / w, ys / h


LX, LY = grid(LW, LH)
ASPECT = H / W


def up(rgb: np.ndarray, alpha: np.ndarray) -> Frame:
    """Half-size layers scaled to full size."""
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    a = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    return np.asarray(img, np.float32) / 255, np.asarray(a, np.float32) / 255


def glow_layer(draw_fn: Callable[[ImageDraw.ImageDraw], None], blur: float, core: float = 1.0) -> np.ndarray:
    """A white mask drawn by ``draw_fn``, plus a blurred glow of it, as 0..1 intensity."""
    mask = Image.new("L", (W, H), 0)
    draw_fn(ImageDraw.Draw(mask))
    glow = mask.filter(ImageFilter.GaussianBlur(blur))
    m = np.asarray(mask, np.float32) / 255
    g = np.asarray(glow, np.float32) / 255
    return np.clip(m * core + g * 1.6, 0, 1)


def tint(intensity: np.ndarray, color: tuple[float, float, float], white_core: float = 0.7) -> Frame:
    """Colour an intensity mask, going to white where it is brightest, as light does."""
    c = np.array(color, np.float32)
    rgb = c * intensity[..., None] + (1 - c) * (intensity[..., None] ** 3) * white_core
    return np.clip(rgb / np.maximum(intensity[..., None], 1e-4), 0, 1), intensity


def smooth_noise(rng: np.random.Generator, cells: int, w: int, h: int) -> np.ndarray:
    small = Image.fromarray((rng.random((cells * 2, cells)) * 255).astype(np.uint8))
    return np.asarray(small.resize((w, h), Image.BICUBIC), np.float32) / 255


# --- the graphics ------------------------------------------------------------------

def light_leak(t: float, rng: np.random.Generator) -> Frame:
    env = bell(t, 0.4, 0.4)
    blobs = [((-0.2 + 1.3 * t, 0.15 + 0.5 * t), 0.42, (1.0, 0.55, 0.2)),
             ((1.1 - 1.2 * t, 0.85 - 0.45 * t), 0.36, (1.0, 0.25, 0.45)),
             ((0.5, 1.2 - 1.1 * t), 0.25, (1.0, 0.8, 0.35))]
    rgb = np.zeros((LH, LW, 3), np.float32)
    alpha = np.zeros((LH, LW), np.float32)
    for (cx, cy), r, color in blobs:
        d2 = (LX - cx) ** 2 + ((LY - cy) * ASPECT) ** 2
        a = np.exp(-d2 / (2 * r * r))
        rgb += a[..., None] * np.array(color, np.float32)
        alpha = 1 - (1 - alpha) * (1 - a)
    rgb = rgb / np.maximum(rgb.max(axis=2, keepdims=True), 1e-4)
    return up(rgb, alpha * env)


def flash_burst(t: float, rng: np.random.Generator) -> Frame:
    radius = 0.05 + 1.4 * ease_out(t / 0.6)
    d = np.sqrt((LX - 0.5) ** 2 + ((LY - 0.5) * ASPECT) ** 2)
    core = np.exp(-(d / max(radius, 1e-3)) ** 2 * 3)
    full = max(0.0, 1 - abs(t - 0.18) / 0.18) * 0.85
    alpha = np.clip(core * bell(t, 0.25) + full, 0, 1)
    warm = np.stack([np.ones_like(d), 0.92 - 0.2 * d, 0.8 - 0.4 * d], axis=-1)
    return up(np.clip(warm, 0, 1), alpha)


def shockwave(t: float, rng: np.random.Generator) -> Frame:
    d = np.sqrt((LX - 0.5) ** 2 + ((LY - 0.5) * ASPECT) ** 2)
    intensity = np.zeros_like(d)
    for k, delay in enumerate((0.0, 0.14, 0.28)):
        u = (t - delay) / 0.7
        if 0 < u < 1:
            r = 0.04 + 1.1 * ease_out(u)
            width = 0.012 + 0.03 * u
            intensity += np.exp(-((d - r) / width) ** 2) * (1 - u) * (1.0 - 0.25 * k)
    intensity = np.clip(intensity, 0, 1)
    rgb, a = tint(intensity, (0.35, 0.85, 1.0))
    return up(rgb, a)


def speed_lines(t: float, rng: np.random.Generator) -> Frame:
    env = bell(t, 0.3)
    step_rng = np.random.default_rng(int(t * FPS) // 2 + 7)
    cx, cy = W / 2, H / 2
    reach = math.hypot(W, H) / 2 + 40

    def draw(d: ImageDraw.ImageDraw) -> None:
        for _ in range(110):
            angle = step_rng.uniform(0, 2 * math.pi)
            inner = reach * step_rng.uniform(0.38, 0.7) * (1.15 - 0.3 * env)
            spread = step_rng.uniform(0.002, 0.008)
            pts = [(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner),
                   (cx + math.cos(angle - spread) * reach, cy + math.sin(angle - spread) * reach),
                   (cx + math.cos(angle + spread) * reach, cy + math.sin(angle + spread) * reach)]
            d.polygon(pts, fill=int(255 * step_rng.uniform(0.6, 1.0)))

    intensity = glow_layer(draw, 3, 1.0) * env
    return np.ones((H, W, 3), np.float32), np.clip(intensity, 0, 1)


def glitch_bars(t: float, rng: np.random.Generator) -> Frame:
    env = bell(t, 0.45, 0.4)
    step_rng = np.random.default_rng(int(t * FPS) // 2 + 11)
    rgb = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    palette = [(0.0, 1.0, 0.95), (1.0, 0.1, 0.75), (1.0, 1.0, 1.0), (0.15, 0.3, 1.0)]
    for _ in range(int(4 + 22 * env)):
        y = int(step_rng.uniform(0, H))
        h = int(step_rng.uniform(6, 110))
        x0 = int(step_rng.uniform(-W * 0.3, W * 0.6))
        x1 = min(W, x0 + int(step_rng.uniform(W * 0.3, W * 1.2)))
        color = palette[step_rng.integers(len(palette))]
        rgb[y:y + h, max(0, x0):x1] = color
        alpha[y:y + h, max(0, x0):x1] = step_rng.uniform(0.45, 0.95)
    alpha[::4] = np.maximum(alpha[::4], 0.18 * env)
    return rgb, alpha * min(1.0, env * 1.4)


def diagonal_swipe(t: float, rng: np.random.Generator) -> Frame:
    rgb = np.zeros((LH, LW, 3), np.float32)
    alpha = np.zeros((LH, LW), np.float32)
    # Distance along the diagonal from bottom-left (0) to top-right (~2).
    s = LX + (1 - LY) * ASPECT * 0.55
    span = 1 + ASPECT * 0.55
    bands = [(0.0, (0.96, 0.62, 0.04)), (0.1, (1.0, 1.0, 1.0)), (0.2, (0.08, 0.08, 0.09))]
    for delay, color in bands:
        u = ease_in_out((t - delay) / 0.75)
        lead = -0.4 + (span + 0.8) * u
        tail = lead - 0.55 - 0.25 * (1 - abs(2 * u - 1))
        tail = max(tail, lead - 0.9) if u < 0.5 else lead - 0.55 * (1 - u) * 2
        inside = (s < lead) & (s > tail)
        rgb[inside] = color
        alpha[inside] = 1.0
    return up(rgb, alpha)


def particle_burst(t: float, rng: np.random.Generator) -> Frame:
    prng = np.random.default_rng(21)
    n = 170
    angle = prng.uniform(0, 2 * math.pi, n)
    speed = prng.uniform(500, 1500, n)
    size = prng.uniform(3, 11, n)
    hue = prng.random(n)
    u = ease_out(t)
    x = W / 2 + np.cos(angle) * speed * u
    y = H / 2 + np.sin(angle) * speed * u + 900 * t * t
    fade = max(0.0, 1 - t ** 1.5)

    def draw(d: ImageDraw.ImageDraw) -> None:
        for xi, yi, si in zip(x, y, size * (1.2 - 0.6 * t)):
            d.ellipse((xi - si, yi - si, xi + si, yi + si), fill=255)

    intensity = glow_layer(draw, 6, 1.0) * fade
    gold = np.array([1.0, 0.78, 0.3], np.float32)
    rgb = np.broadcast_to(gold, (H, W, 3)).copy()
    rgb = rgb + (1 - rgb) * (intensity[..., None] > 0.9)
    _ = hue
    return rgb, np.clip(intensity, 0, 1)


def lens_flare(t: float, rng: np.random.Generator) -> Frame:
    cx = -0.2 + 1.4 * ease_in_out(t)
    cy = 0.42
    dy = (LY - cy) * ASPECT
    streak = np.exp(-(dy / 0.008) ** 2) * np.exp(-((LX - cx) / 0.9) ** 2)
    halo = np.exp(-(((LX - cx) ** 2 + dy ** 2) / 0.012))
    ghosts = sum(np.exp(-(((LX - (1 - cx) * k) ** 2 + ((LY - (1 - cy) * k) * ASPECT) ** 2) / (0.002 + 0.002 * k)))
                 * 0.35 for k in (0.6, 0.9, 1.2))
    intensity = np.clip(streak * 1.2 + halo + ghosts, 0, 1) * bell(t, 0.5, 0.5)
    rgb, a = tint(intensity, (0.45, 0.7, 1.0), white_core=0.9)
    return up(rgb, a)


def bokeh(t: float, rng: np.random.Generator) -> Frame:
    prng = np.random.default_rng(5)
    n = 38
    xs, ys = prng.uniform(0, 1, n), prng.uniform(0, 1, n)
    rs = prng.uniform(0.025, 0.09, n)
    rise = prng.uniform(0.05, 0.2, n)
    colors = np.array([(1.0, 0.75, 0.3), (1.0, 0.55, 0.4), (1.0, 0.9, 0.6)], np.float32)[prng.integers(3, size=n)]
    rgb = np.zeros((LH, LW, 3), np.float32)
    alpha = np.zeros((LH, LW), np.float32)
    for x, y, r, v, c in zip(xs, ys, rs, rise, colors):
        d = np.sqrt((LX - x) ** 2 + ((LY - (y - v * t)) * ASPECT) ** 2)
        disc = np.clip((r - d) / (r * 0.25), 0, 1) * 0.55
        rgb += disc[..., None] * c
        alpha = 1 - (1 - alpha) * (1 - disc)
    rgb = rgb / np.maximum(rgb.max(axis=2, keepdims=True), 1e-4)
    return up(rgb, alpha * bell(t, 0.45, 0.5))


def film_burn(t: float, rng: np.random.Generator) -> Frame:
    noise = smooth_noise(np.random.default_rng(3), 6, LW, LH)
    edge = np.minimum.reduce([LX, 1 - LX, LY, 1 - LY]) * 2
    # The burn creeps in from the edges and never reaches the middle third.
    reach = 0.42 * bell(t, 0.5, 0.5)
    heat = np.clip((reach - edge + 0.3 * (noise - 0.5)) / 0.3, 0, 1)
    # Deep amber at the front, brightening to a hot yellow where it has burned longest.
    rgb = np.stack([np.ones_like(heat), 0.3 + 0.55 * heat, 0.02 + 0.35 * heat ** 2], axis=-1)
    return up(rgb, np.clip(heat * 1.4, 0, 0.92))


def neon_frame(t: float, rng: np.random.Generator) -> Frame:
    inset = 70
    progress = ease_in_out(t / 0.55)
    fade = 1 - max(0.0, (t - 0.75) / 0.25)
    perimeter = [(inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset), (inset, inset)]
    lengths = [math.dist(a, b) for a, b in zip(perimeter, perimeter[1:])]
    total = sum(lengths)

    def path(fraction: float) -> list[tuple[float, float]]:
        left = total * fraction
        pts = [perimeter[0]]
        for (a, b), length in zip(zip(perimeter, perimeter[1:]), lengths):
            if left <= 0:
                break
            k = min(1.0, left / length)
            pts.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
            left -= length
        return pts

    pts = path(progress)

    def pink(d: ImageDraw.ImageDraw) -> None:
        if len(pts) > 1:
            d.line(pts, fill=255, width=12, joint="curve")

    shifted = [(x + 18, y + 18) for x, y in pts]

    def cyan(d: ImageDraw.ImageDraw) -> None:
        if len(shifted) > 1:
            d.line(shifted, fill=255, width=6, joint="curve")

    p = glow_layer(pink, 18) * fade
    c = glow_layer(cyan, 14) * fade
    rgb = (p[..., None] * np.array([1.0, 0.2, 0.7]) + c[..., None] * np.array([0.1, 0.95, 1.0]))
    alpha = np.clip(np.maximum(p, c), 0, 1)
    return np.clip(rgb / np.maximum(alpha[..., None], 1e-4), 0, 1).astype(np.float32), alpha


def zoom_tunnel(t: float, rng: np.random.Generator) -> Frame:
    env = bell(t, 0.35, 0.4)

    def draw(d: ImageDraw.ImageDraw) -> None:
        for k in range(7):
            phase = (t * 1.6 + k / 7) % 1
            scale = 0.05 + phase ** 2 * 1.3
            w, h = W * scale, H * scale
            width = max(2, int(4 + 22 * phase))
            d.rounded_rectangle((W / 2 - w / 2, H / 2 - h / 2, W / 2 + w / 2, H / 2 + h / 2),
                                radius=int(40 * scale + 8), outline=int(255 * (0.4 + 0.6 * phase)), width=width)

    intensity = glow_layer(draw, 8) * env
    rgb, a = tint(intensity, (1.0, 0.72, 0.15))
    return rgb, a


def vhs_scan(t: float, rng: np.random.Generator) -> Frame:
    env = bell(t, 0.4, 0.5)
    frame_rng = np.random.default_rng(int(t * FPS) + 31)
    band_y = (t * 1.3) % 1.2 - 0.1
    band = np.exp(-((LY - band_y) / 0.05) ** 2)
    noise = frame_rng.random((LH, LW)).astype(np.float32)
    lines = (np.arange(LH) % 3 == 0).astype(np.float32)[:, None] * np.ones((1, LW), np.float32)
    alpha = np.clip(lines * 0.22 + band * (0.35 + 0.5 * noise), 0, 1) * env
    tint_rgb = np.stack([0.8 + 0.2 * noise, 0.85 * np.ones_like(noise), 1.0 * np.ones_like(noise)], axis=-1)
    tint_rgb[lines > 0] = (0.02, 0.02, 0.05)
    return up(tint_rgb, alpha)


def confetti(t: float, rng: np.random.Generator) -> Frame:
    prng = np.random.default_rng(13)
    n = 140
    x0 = prng.uniform(0, W, n)
    vx = prng.uniform(-200, 200, n)
    vy = prng.uniform(-900, -300, n)
    spin = prng.uniform(-12, 12, n)
    size = prng.uniform(14, 30, n)
    palette = [(245, 158, 11), (255, 255, 255), (236, 72, 153), (59, 130, 246), (34, 197, 94)]
    colors = [palette[i] for i in prng.integers(len(palette), size=n)]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fade = 1 - max(0.0, (t - 0.7) / 0.3)
    for i in range(n):
        x = x0[i] + vx[i] * t
        y = H * 0.05 + vy[i] * t + 2600 * t * t * 0.5 + prng.uniform(-100, 0)
        a = spin[i] * t
        w, h = size[i], size[i] * 0.45 * abs(math.cos(a * 2)) + 2
        pts = [(x + math.cos(a) * dx - math.sin(a) * dy, y + math.sin(a) * dx + math.cos(a) * dy)
               for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
        d.polygon(pts, fill=(*colors[i], int(255 * fade)))
    arr = np.asarray(img, np.float32) / 255
    return arr[..., :3], arr[..., 3]


def lightning(t: float, rng: np.random.Generator) -> Frame:
    visible = 0.08 < t < 0.6 and (int(t * FPS) % 3 != 1)
    bolt_rng = np.random.default_rng(int(t * FPS) // 3 + 41)

    def bolt(start: tuple[float, float], end: tuple[float, float], depth: int) -> list[tuple[float, float]]:
        pts = [start, end]
        offset = W * 0.18
        for _ in range(depth):
            new = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                mid = ((a[0] + b[0]) / 2 + bolt_rng.uniform(-offset, offset), (a[1] + b[1]) / 2)
                new += [mid, b]
            pts = new
            offset *= 0.55
        return pts

    main = bolt((W * bolt_rng.uniform(0.3, 0.7), -20), (W * bolt_rng.uniform(0.3, 0.7), H * 0.85), 7)
    branches = [bolt(main[i], (main[i][0] + bolt_rng.uniform(-300, 300), main[i][1] + bolt_rng.uniform(200, 500)), 5)
                for i in bolt_rng.integers(10, len(main) - 10, 3)]

    def draw(d: ImageDraw.ImageDraw) -> None:
        if visible:
            d.line(main, fill=255, width=7)
            for b in branches:
                d.line(b, fill=200, width=3)

    intensity = glow_layer(draw, 16)
    flash = (0.28 if visible else 0.0) * (1 - t)
    alpha = np.clip(intensity + flash, 0, 1)
    rgb, _ = tint(np.maximum(intensity, 1e-3), (0.55, 0.7, 1.0), white_core=1.0)
    rgb = np.where(intensity[..., None] > 0.02, rgb, np.array([0.6, 0.7, 1.0], np.float32))
    return rgb.astype(np.float32), alpha


def iris_wipe(t: float, rng: np.random.Generator) -> Frame:
    d = np.sqrt((LX - 0.5) ** 2 + ((LY - 0.5) * ASPECT) ** 2)
    full = math.hypot(0.5, 0.5 * ASPECT)
    radius = full * (1 - ease_in_out(t / 0.45)) if t < 0.5 else full * ease_in_out((t - 0.55) / 0.45)
    radius = max(radius, 0.0)
    outside = np.clip((d - radius) / 0.006, 0, 1)
    ring = np.exp(-((d - radius) / 0.01) ** 2) * (radius > 0.001)
    rgb = np.zeros((LH, LW, 3), np.float32) + ring[..., None] * np.array([0.96, 0.62, 0.04], np.float32)
    return up(rgb, np.clip(outside + ring, 0, 1))


# --- sound effects -------------------------------------------------------------------

T = np.arange(int(SR * SECONDS)) / SR


def _env(attack: float, decay: float) -> np.ndarray:
    return np.minimum(1, T / max(attack, 1e-4)) * np.exp(-np.maximum(0, T - attack) / max(decay, 1e-4))


def _noise(seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(T.size)


def _band(signal: np.ndarray, low: float, high: float) -> np.ndarray:
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(signal.size, 1 / SR)
    spectrum[(freqs < low) | (freqs > high)] = 0
    return np.fft.irfft(spectrum, signal.size)


def _sweep_noise(seed: int, f0: float, f1: float, shape: np.ndarray) -> np.ndarray:
    """Noise whose centre frequency glides from f0 to f1 (by blending bands)."""
    n = _noise(seed)
    bands = [_band(n, f * 0.6, f * 1.6) for f in np.geomspace(f0, f1, 8)]
    pos = np.clip(T / SECONDS, 0, 1) * (len(bands) - 1)
    out = np.zeros_like(T)
    for i, b in enumerate(bands):
        out += b * np.clip(1 - abs(pos - i), 0, 1)
    return out * shape


def _tone(freq: np.ndarray | float, shape: np.ndarray) -> np.ndarray:
    phase = 2 * np.pi * np.cumsum(np.broadcast_to(freq, T.shape)) / SR
    return np.sin(phase) * shape


def _swell(peak: float) -> np.ndarray:
    return np.where(T < peak, (T / peak) ** 2, np.exp(-(T - peak) / 0.12))


SFX: dict[str, Callable[[], tuple[np.ndarray, np.ndarray]]] = {}


def sfx(name: str):
    def register(fn):
        SFX[name] = fn
        return fn
    return register


def _mono(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return x, x


@sfx("shimmer_swell")
def _():
    bells = sum(_tone(f, _env(0.25, 0.5)) * 0.15 for f in (1318.5, 1760, 2637, 3520))
    return _mono(bells + _sweep_noise(1, 3000, 9000, _swell(0.35)) * 0.4)


@sfx("flash_hit")
def _():
    return _mono(_band(_noise(2), 1500, 12000) * _env(0.002, 0.08) + _tone(55 * np.exp(-T * 3), _env(0.003, 0.25)) * 0.9)


@sfx("boom_wave")
def _():
    rumble = _band(_noise(3), 30, 180) * _env(0.01, 0.5) * 2.0
    return _mono(_tone(70 * np.exp(-T * 2.2) + 30, _env(0.005, 0.45)) + rumble)


@sfx("speed_whoosh")
def _():
    x = _sweep_noise(4, 300, 6000, _swell(0.3)) * 1.4
    pan = np.clip(T / 0.5, 0, 1)
    return x * (1 - pan * 0.6), x * (0.4 + pan * 0.6)


@sfx("glitch_stutter")
def _():
    gate = (np.floor(T * 24) % 2 == 0) & (T < 0.55)
    tone = np.sign(np.sin(2 * np.pi * (220 + 440 * (np.floor(T * 12) % 3)) * T))
    crushed = np.round(_noise(5) * 4) / 4
    return _mono((tone * 0.35 + crushed * 0.2) * gate * _env(0.002, 0.4))


@sfx("swipe_air")
def _():
    x = _sweep_noise(6, 800, 5000, np.exp(-((T - 0.18) / 0.09) ** 2)) * 1.8
    pan = np.clip(T / 0.35, 0, 1)
    return x * (1 - pan), x * pan


@sfx("sparkle_burst")
def _():
    rng = np.random.default_rng(7)
    out = np.zeros_like(T)
    for _ in range(26):
        start = rng.uniform(0.0, 0.5)
        f = rng.uniform(2500, 6500)
        local = np.clip(T - start, 0, None)
        out += np.sin(2 * np.pi * f * local) * np.exp(-local / 0.05) * (T >= start) * 0.18
    return out * 0.9, np.roll(out, 240) * 0.9


@sfx("flare_swoosh")
def _():
    return _mono(_tone(400 + 1800 * T, _swell(0.5) * 0.25) + _sweep_noise(8, 1500, 7000, _swell(0.5)) * 0.6)


@sfx("soft_chime")
def _():
    return _mono(sum(_tone(f, _env(0.005, 0.6)) * a for f, a in ((1046.5, 0.35), (1568, 0.2), (2093, 0.12), (3136, 0.06))))


@sfx("burn_crackle")
def _():
    rng = np.random.default_rng(9)
    crackle = np.zeros_like(T)
    idx = rng.integers(0, T.size, 140)
    crackle[idx] = rng.uniform(-1, 1, idx.size)
    crackle = _band(crackle, 1500, 10000) * 6
    return _mono(crackle * _swell(0.5) + _sweep_noise(10, 200, 1200, _swell(0.5)) * 0.6)


@sfx("neon_buzz")
def _():
    buzz = np.sign(np.sin(2 * np.pi * 120 * T)) * 0.12 * _swell(0.45)
    return _mono(buzz + _tone(300 + 500 * np.clip(T / 0.5, 0, 1), _swell(0.5) * 0.2))


@sfx("tunnel_rush")
def _():
    riser = _tone(180 * (1 + 3 * T ** 2), _swell(0.55) * 0.3)
    return _mono(riser + _sweep_noise(11, 400, 8000, _swell(0.55)) * 0.8)


@sfx("tape_rewind")
def _():
    warble = 600 + 350 * np.sin(2 * np.pi * 7 * T) - 400 * T
    return _mono(np.sign(np.sin(2 * np.pi * np.cumsum(warble) / SR)) * 0.12 * _env(0.01, 0.5)
                 + _band(_noise(12), 2000, 8000) * 0.15 * _env(0.01, 0.4))


@sfx("pop_party")
def _():
    pop = _tone(900 * np.exp(-T * 25) + 300, _env(0.001, 0.05)) * 0.9
    return np.add(pop, SFX["sparkle_burst"]()[0] * 0.6), np.add(pop, SFX["sparkle_burst"]()[1] * 0.6)


@sfx("thunder_zap")
def _():
    crack = _band(_noise(13), 2000, 14000) * _env(0.001, 0.05) * 1.5
    rumble = _band(_noise(14), 25, 150) * np.exp(-((T - 0.35) / 0.25) ** 2) * 2.5
    return _mono(crack + rumble + _tone(60, _env(0.005, 0.3)) * 0.5)


@sfx("iris_thump")
def _():
    hit = _tone(80 * np.exp(-T * 8) + 40, _env(0.002, 0.12))
    second = np.roll(hit, int(SR * 0.5)) * (T >= 0.5)
    return _mono(hit + second * 0.8)


# --- the library ------------------------------------------------------------------

@dataclass(frozen=True)
class Graphic:
    id: str
    name: str
    draw: Callable[[float, np.random.Generator], Frame]
    sfx: str
    moods: tuple[str, ...]


LIBRARY = [
    Graphic("light_leak", "Light Leak", light_leak, "shimmer_swell", ("story", "emotional", "general")),
    Graphic("flash_burst", "Flash Burst", flash_burst, "flash_hit", ("shock", "hype", "general")),
    Graphic("shockwave", "Shockwave", shockwave, "boom_wave", ("shock", "hype", "money")),
    Graphic("speed_lines", "Speed Lines", speed_lines, "speed_whoosh", ("hype", "sports", "gaming")),
    Graphic("glitch_bars", "Glitch Bars", glitch_bars, "glitch_stutter", ("tech", "gaming", "shock")),
    Graphic("diagonal_swipe", "Diagonal Swipe", diagonal_swipe, "swipe_air", ("general", "educational", "news")),
    Graphic("particle_burst", "Particle Burst", particle_burst, "sparkle_burst", ("hype", "money", "funny")),
    Graphic("lens_flare", "Lens Flare", lens_flare, "flare_swoosh", ("story", "music", "general")),
    Graphic("bokeh", "Bokeh Drift", bokeh, "soft_chime", ("emotional", "story", "food")),
    Graphic("film_burn", "Film Burn", film_burn, "burn_crackle", ("story", "music", "emotional")),
    Graphic("neon_frame", "Neon Frame", neon_frame, "neon_buzz", ("tech", "music", "gaming")),
    Graphic("zoom_tunnel", "Zoom Tunnel", zoom_tunnel, "tunnel_rush", ("question", "educational", "hype")),
    Graphic("vhs_scan", "VHS Scan", vhs_scan, "tape_rewind", ("funny", "story", "podcast")),
    Graphic("confetti", "Confetti Pop", confetti, "pop_party", ("funny", "hype", "money")),
    Graphic("lightning", "Lightning", lightning, "thunder_zap", ("shock", "sports", "hype")),
    Graphic("iris_wipe", "Iris Wipe", iris_wipe, "iris_thump", ("question", "podcast", "general")),
]


def write_graphic(graphic: Graphic) -> None:
    out = OUT_DIR / f"{graphic.id}.mp4"
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W * 2}x{H}",
        "-framerate", str(FPS), "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ], stdin=subprocess.PIPE)
    rng = np.random.default_rng(0)
    for index in range(FRAMES):
        rgb, alpha = graphic.draw(index / (FRAMES - 1), rng)
        alpha = np.clip(alpha, 0, 1)
        colour = (np.clip(rgb, 0, 1) * alpha[..., None] ** 0 * 255).astype(np.uint8)
        colour[alpha < 1 / 255] = 0
        matte = np.repeat((alpha * 255).astype(np.uint8)[..., None], 3, axis=2)
        proc.stdin.write(np.concatenate([colour, matte], axis=1).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {graphic.id}")


def write_sfx(name: str) -> None:
    left, right = SFX[name]()
    stereo = np.stack([left, right], axis=1)
    peak = np.abs(stereo).max() or 1.0
    fade = np.minimum(1, (T[::-1] / 0.05))[:, None]
    pcm = (stereo / peak * 0.7 * fade * 32767).astype(np.int16)
    path = OUT_DIR / "sfx" / f"{name}.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(pcm.tobytes())


def main() -> None:
    (OUT_DIR / "sfx").mkdir(parents=True, exist_ok=True)
    for graphic in LIBRARY:
        write_graphic(graphic)
        write_sfx(graphic.sfx)
        print(f"rendered {graphic.id}")
    manifest = {
        "version": 1,
        "width": W, "height": H, "fps": FPS, "duration": SECONDS, "layout": "packed_alpha_side_by_side",
        "graphics": [
            {"id": g.id, "name": g.name, "file": f"{g.id}.mp4", "sfx": f"sfx/{g.sfx}.wav", "moods": list(g.moods)}
            for g in LIBRARY
        ],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
