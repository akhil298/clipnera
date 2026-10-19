"""Colour grades for finished Pro clips, as 3D LUTs written by code (no licence to clear).

The reels' "after" is never flat: warm skin, teal-leaning shadows, a little
contrast. Each grade is a small function on RGB baked into a ``.cube`` file
the first time it is used, then applied with FFmpeg's ``lut3d``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from beats.kit import kit_dir

SIZE = 17
Grade = Callable[[np.ndarray], np.ndarray]


def _s_curve(x: np.ndarray, amount: float) -> np.ndarray:
    """Contrast around mid-grey: ``amount`` 0 leaves it alone."""
    return np.clip(x + amount * (x - 0.5) * (1 - np.abs(2 * x - 1)), 0, 1)


def _saturate(rgb: np.ndarray, amount: float) -> np.ndarray:
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722])
    return np.clip(luma[..., None] + (rgb - luma[..., None]) * (1 + amount), 0, 1)


def _split_tone(rgb: np.ndarray, shadows: tuple[float, float, float], highlights: tuple[float, float, float], amount: float) -> np.ndarray:
    luma = (rgb @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    shade = np.array(shadows) * (1 - luma) + np.array(highlights) * luma
    return np.clip(rgb + amount * (shade - 0.5) * (1 - np.abs(2 * luma - 1)) * 2, 0, 1)


def teal_orange(rgb: np.ndarray) -> np.ndarray:
    rgb = _split_tone(rgb, (0.30, 0.52, 0.58), (0.68, 0.52, 0.36), 0.12)
    return _saturate(_s_curve(rgb, 0.35), 0.12)


def clean_bright(rgb: np.ndarray) -> np.ndarray:
    lifted = np.clip(rgb * 1.04 + 0.015, 0, 1)
    return _saturate(_s_curve(_split_tone(lifted, (0.48, 0.5, 0.53), (0.56, 0.51, 0.46), 0.06), 0.22), 0.08)


def moody(rgb: np.ndarray) -> np.ndarray:
    rgb = _split_tone(np.clip(rgb * 0.96, 0, 1), (0.30, 0.42, 0.62), (0.62, 0.52, 0.42), 0.14)
    return _saturate(_s_curve(rgb, 0.45), -0.05)


def warm_film(rgb: np.ndarray) -> np.ndarray:
    rgb = _split_tone(rgb, (0.42, 0.40, 0.36), (0.66, 0.55, 0.40), 0.12)
    faded = 0.04 + rgb * 0.93
    return _saturate(_s_curve(faded, 0.25), -0.04)


GRADES: dict[str, Grade] = {"teal_orange": teal_orange, "clean_bright": clean_bright, "moody": moody, "warm_film": warm_film}
# The grade each beat theme gets.
THEME_GRADE = {"clean": "teal_orange", "bold": "clean_bright", "dark": "moody", "editorial": "warm_film"}


def lut_path(theme: str) -> Path:
    """The ``.cube`` file for the theme's grade, written on first use."""
    name = THEME_GRADE.get(theme, "teal_orange")
    path = kit_dir() / "luts" / f"{name}.cube"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_cube(GRADES[name], path)
    return path


def write_cube(grade: Grade, path: Path, size: int = SIZE) -> None:
    axis = np.linspace(0.0, 1.0, size)
    # .cube order: red varies fastest, then green, then blue.
    b, g, r = np.meshgrid(axis, axis, axis, indexing="ij")
    rgb = np.stack([r, g, b], axis=-1).reshape(-1, 3)
    out = grade(rgb)
    lines = [f'TITLE "{path.stem}"', f"LUT_3D_SIZE {size}", *(f"{x:.5f} {y:.5f} {z:.5f}" for x, y, z in out)]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="ascii")
    tmp.replace(path)
