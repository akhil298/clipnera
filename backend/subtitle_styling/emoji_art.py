"""Colour emoji in burned captions, drawn as ASS vector shapes.

libass draws no colour fonts, so an emoji burned as a box, or as a one-colour
outline in an emoji font. Twemoji's COLR font keeps every emoji as flat colour
layers, and each layer becomes an ASS drawing. A line with emoji is written
once with an empty drawing the emoji's size holding its place, then once per
colour layer on a higher Layer with its text invisible: every copy lays out
the same, so the layers stack into the full-colour emoji beside its word.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

FONT = Path(__file__).resolve().parent.parent / "static" / "fonts" / "Twemoji.Mozilla.ttf"
# The one-colour face for an emoji Twemoji does not have.
MONO_FAMILY = "Noto Emoji"
# Colour layers sit above the captions (1) and the title (2).
FIRST_LAYER = 3
# Twemoji draws in a 512-unit square from y=-64 to y=448.
EM, TOP = 512, 448
# Drawings use \p3, quarter pixels, so curves stay smooth in whole numbers.
SUB = 4
# Marks an upcoming word's emoji: it holds its place but is not drawn yet.
GHOST = "\ue000"

_BASE = "\u2300-\u23ff\u2600-\u27bf\u2b00-\u2bff\U0001f000-\U0001faff"
_MOD = "\ufe0f\U0001f3fb-\U0001f3ff"
# An emoji already set in the one-colour face is left alone, so a second pass changes nothing.
_MONO_TAG = re.escape(f"\\fn{MONO_FAMILY}}}")
EMOJI = re.compile(f"(?<!{_MONO_TAG}){GHOST}?(?:[\U0001f1e6-\U0001f1ff]{{2}}|[{_BASE}][{_MOD}]*(?:\u200d[{_BASE}][{_MOD}]*)*)")
# Alpha does not change layout, so the colour copies drop it to keep their text hidden.
_ALPHA = re.compile(r"\\(?:alpha|[1-4]a)&H[0-9A-Fa-f]{2}&")
# The alpha tags (and resets) a line sets, to restore them after a hidden placeholder.
_ALPHA_STATE = re.compile(r"\\(alpha|1a|3a|4a)&H([0-9A-Fa-f]{2})&|\\r(?![a-zA-Z])")
_FONT_SIZE = re.compile(r"\\fs(\d+(?:\.\d+)?)")
_FONT_NAME = re.compile(r"\\fn([^\\}]+)")


class _AssPen(BasePen):
    """Glyph outlines as ASS drawing commands, y flipped and scaled to quarter pixels."""

    def __init__(self, glyph_set: Any, scale: float) -> None:
        super().__init__(glyph_set)
        self._scale = scale
        self.parts: list[str] = []

    def _xy(self, point: tuple[float, float]) -> str:
        return f"{round(point[0] * self._scale)} {round((TOP - point[1]) * self._scale)}"

    def _moveTo(self, pt):
        self.parts.append(f"m {self._xy(pt)}")

    def _lineTo(self, pt):
        self.parts.append(f"l {self._xy(pt)}")

    def _curveToOne(self, pt1, pt2, pt3):
        self.parts.append(f"b {self._xy(pt1)} {self._xy(pt2)} {self._xy(pt3)}")


@lru_cache(maxsize=1)
def _font() -> tuple[Any, list[Any], dict[str, list[Any]], dict[int, str]]:
    font = TTFont(FONT)
    return font.getGlyphSet(), font["CPAL"].palettes[0], font["COLR"].ColorLayers, font.getBestCmap()


def _glyph(emoji: str) -> str | None:
    """Twemoji's colour glyph for ``emoji``, a sequence first, then its first character."""
    _, _, colour_layers, cmap = _font()
    codes = [f"{ord(c):x}" for c in emoji]
    for seq in (codes, [c for c in codes if c != "fe0f"]):
        if (name := "u" + "_".join(seq)) in colour_layers:
            return name
    name = cmap.get(ord(emoji[0]))
    return name if name in colour_layers else None


def _box(px: int) -> str:
    """Two specks a quarter pixel wide at opposite corners of the emoji's square.

    libass sizes a drawing by what it draws, ignoring bare moves, so these give
    every copy of an emoji the same square and so the same place in the line.
    """
    return f"m 0 0 l 1 0 l 0 1 m {px} {px} l {px - 1} {px} l {px} {px - 1}"


def _alphas(style: list[str], before: str) -> dict[str, str]:
    """The fill, outline and shadow alpha in force at the end of ``before``."""
    initial = {"1a": style[3][2:4], "3a": style[5][2:4], "4a": style[6][2:4]}
    state = dict(initial)
    for match in _ALPHA_STATE.finditer(before):
        tag, value = match.groups()
        if tag is None:
            state = dict(initial)
        elif tag == "alpha":
            state = dict.fromkeys(state, value)
        else:
            state[tag] = value
    return state


@lru_cache(maxsize=1024)
def layers(emoji: str, size: int) -> tuple[tuple[str, str], ...]:
    """(ASS colour, drawing) for each colour layer of ``emoji`` at ``size`` px; empty without art."""
    name = _glyph(emoji)
    if name is None:
        return ()
    glyph_set, palette, colour_layers, _ = _font()
    px = size * SUB
    out = []
    for layer in colour_layers[name]:
        pen = _AssPen(glyph_set, px / EM)
        glyph_set[layer.name].draw(pen)
        c = palette[layer.colorID] if layer.colorID < len(palette) else None
        colour = f"&H{c.blue:02X}{c.green:02X}{c.red:02X}&" if c else "&H000000&"
        out.append((colour, f"{_box(px)} {' '.join(pen.parts)}"))
    return tuple(out)


def _transparent(style_line: str) -> str:
    """A copy of ``style_line`` named ``<name>Emoji`` with every colour fully transparent."""
    fields = style_line[len("Style: "):].split(",")
    fields[0] += "Emoji"
    for i in range(3, 7):
        fields[i] = "&HFF" + fields[i][4:]
    return "Style: " + ",".join(fields)


def _expand(fields: list[str], styles: dict[str, list[str]]) -> list[str]:
    """One Dialogue (split into its ten fields) as its own line plus a copy per colour layer."""
    style, text = styles[fields[3]], fields[9]
    # A see-through style (a box layer) only needs the emoji's space, not its colour.
    coloured = not style[3].startswith("&HFF")
    found = []
    for match in EMOJI.finditer(text):
        before = text[:match.start()]
        sizes, names = _FONT_SIZE.findall(before), _FONT_NAME.findall(before)
        size = round(float(sizes[-1] if sizes else style[2]))
        ghost = match.group().startswith(GHOST)
        emoji = match.group().lstrip(GHOST)
        found.append((emoji, size, ghost, layers(emoji, size), names[-1] if names else style[1],
                      _alphas(style, before)))

    # On an opaque-box style the box should still cover the emoji, so only its fill hides.
    boxed = style[15] == "3"

    def render(layer: int | None) -> str:
        pieces = iter(found)

        def one(_: re.Match) -> str:
            emoji, size, ghost, art, family, alpha = next(pieces)
            if not art:
                return f"{{\\fn{MONO_FAMILY}}}{emoji}{{\\fn{family}}}"
            if layer is None:
                hide = "\\1a&HFF&" if boxed else "\\1a&HFF&\\3a&HFF&\\4a&HFF&"
                restore = "".join(f"\\{tag}&H{value}&" for tag, value in alpha.items())
                return f"{{{hide}\\p3}}{_box(size * SUB)}{{\\p0{restore}}}"
            if ghost or not coloured or layer >= len(art):
                return f"{{\\p3}}{_box(size * SUB)}{{\\p0}}"
            colour, drawing = art[layer]
            return f"{{\\1a&H00&\\c{colour}\\p3}}{drawing}{{\\p0\\1a&HFF&}}"

        return EMOJI.sub(one, text if layer is None else _ALPHA.sub("", text))

    lines = [",".join([*fields[:9], render(None)])]
    if coloured:
        depth = max((len(art) for _, _, ghost, art, _, _ in found if not ghost), default=0)
        for k in range(depth):
            copy = [str(FIRST_LAYER + k), *fields[1:3], f"{fields[3]}Emoji", *fields[4:9], render(k)]
            lines.append(",".join(copy))
    return [f"Dialogue: {line}" for line in lines]


def colourize(ass: str) -> str:
    """``ass`` with every emoji in its Dialogue lines drawn in full colour."""
    lines = ass.split("\n")
    if not any(line.startswith("Dialogue: ") and EMOJI.search(line) for line in lines):
        return ass
    styles = {line[len("Style: "):].split(",")[0]: line for line in lines if line.startswith("Style: ")}
    fields_of = {name: line[len("Style: "):].split(",") for name, line in styles.items()}
    out: list[str] = []
    used: set[str] = set()
    for line in lines:
        if line.startswith("Dialogue: ") and EMOJI.search(line):
            fields = line[len("Dialogue: "):].split(",", 9)
            used.add(fields[3])
            out.extend(_expand(fields, fields_of))
        else:
            out.append(line)
    last_style = max(i for i, line in enumerate(out) if line.startswith("Style: "))
    out[last_style + 1:last_style + 1] = [_transparent(styles[name]) for name in sorted(used)]
    return "\n".join(out)
