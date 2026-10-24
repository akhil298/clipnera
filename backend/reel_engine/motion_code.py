"""Motion code: a graphic the model designs and writes itself, instead of filling in one of our templates.

The model (Astra) sees the frame and the line being said and writes the graphic as HTML + CSS (+ inline SVG): kinetic
type, a drawn chart, a counter, an icon sketched in strokes. The code is cleaned to an allowlist (no script, no
handlers, no outside URLs), rendered by the beats renderer's ``code`` template (a closed shadow root, every CSS
animation paused at each frame), laid over the footage, and looked at by a second model. Its problems go back to the
designer, which rewrites the graphic; the best try is kept. It is the loop a human motion designer runs: build,
render, look, fix.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine import typekits
from reel_engine.render import FPS, H, W, _draw

log = get_logger(__name__)

TRIES = 3
PASS_SCORE = 8      # a try the checker scores this or more ships without another round
MAX_CODE = 24000    # characters of HTML + CSS
LOOK_AT = (0.3, 0.6, 0.9)  # shares of the graphic's length the checker sees

TAGS = {
    "div", "span", "p", "b", "i", "em", "strong", "br", "h1", "h2", "h3", "svg", "g", "path", "circle", "ellipse", "rect",
    "line", "polyline", "polygon", "text", "tspan", "defs", "lineargradient", "radialgradient", "stop", "clippath", "mask",
    "filter", "fegaussianblur", "feoffset", "femerge", "femergenode", "fedropshadow", "fecolormatrix", "feblend",
}
VOID = {"br", "stop", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "fegaussianblur", "feoffset",
        "femergenode", "fedropshadow", "fecolormatrix", "feblend"}
ATTRS = {
    "class", "id", "style", "viewbox", "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "width", "height",
    "points", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset",
    "opacity", "transform", "offset", "stop-color", "stop-opacity", "gradientunits", "gradienttransform", "clip-path", "mask",
    "filter", "stddeviation", "dx", "dy", "text-anchor", "dominant-baseline", "font-size", "font-weight", "font-family",
    "letter-spacing", "preserveaspectratio", "fill-opacity", "stroke-opacity", "xmlns", "pathlength", "in", "in2", "result",
    "flood-color", "flood-opacity", "values", "mode", "type",
}
# Anything that could run code or reach outside the page; url(#id) (an SVG gradient or clip in the same graphic) is fine.
BANNED = re.compile(r"javascript:|expression\s*\(|@import|behavior\s*:|-moz-binding|url\(\s*['\"]?(?!#)|</style|<script", re.I)


class Rejected(ValueError):
    """Code that breaks the allowlist; the designer is told why and tries again."""


class _Clean(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.dropped: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in TAGS:
            self.dropped.add(tag)
            return
        kept = []
        for name, value in attrs:
            value = value or ""
            if name not in ATTRS or BANNED.search(value):
                self.dropped.add(f"{tag}[{name}]")
                continue
            kept.append(f' {name}="{escape(value, quote=True)}"')
        self.out.append(f"<{tag}{''.join(kept)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag in TAGS and tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in TAGS and tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.out.append(escape(data, quote=False))


def clean(html: str, css: str) -> tuple[str, str]:
    """The graphic's HTML rebuilt from allowed tags and attributes only, and its CSS if it is safe; Rejected otherwise."""
    if len(html) + len(css) > MAX_CODE:
        raise Rejected(f"the code is longer than {MAX_CODE} characters")
    if BANNED.search(css):
        raise Rejected("the CSS uses an outside url(), @import or script; draw everything inline")
    parser = _Clean()
    parser.feed(html)
    parser.close()
    if {"script", "iframe", "img", "object", "embed", "link", "style", "foreignobject", "animate"} & parser.dropped:
        raise Rejected(f"not allowed: {', '.join(sorted(parser.dropped))}; use HTML, CSS animations and inline SVG only")
    return "".join(parser.out), css


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MotionCode(_M):
    html: str
    css: str
    why: str


class Look(_M):
    score: int
    problems: list[str]


SYSTEM = """You are a senior motion designer for premium short-form video (the $120 edits top creators pay for).
You design ONE motion graphic for a moment of a vertical reel and write it as code: HTML + CSS, with inline SVG for
shapes, icons, charts and strokes. It is rendered frame by frame on a transparent 1080x1920 canvas and laid over
the footage you are shown.

What a great graphic does: it SHOWS the idea being said (a number counts up, a list builds, a chart draws itself, a
word slams in, a strike-through crosses out the myth, an arrow points at what matters), it lands on the spoken word,
it reads in under a second on a phone, and it looks designed for this video, not like a template.

THE CODE CONTRACT (anything else is stripped or rejected):
- html: one root <div class="mg"> holding divs, spans, headings and inline <svg> (path, circle, rect, line, polyline,
  polygon, text, g, defs, gradients, clipPath, mask, simple filters). No <script>, <img>, <style>, <iframe>, no on*=
  handlers, no SMIL <animate>, no external URLs (url(#id) inside your own SVG is fine).
- css: plain CSS for that html. ALL motion is CSS @keyframes with explicit animation-delay and animation-duration in
  seconds measured from the graphic's start, animation-fill-mode: both. Time entrances to the word timings given.
  Counters: @property --n { syntax: '<integer>'; initial-value: 0; inherits: false; } animated in @keyframes and shown
  with counter-reset: n var(--n) and content: counter(n) on a ::after. Draw-on strokes: stroke-dasharray /
  stroke-dashoffset with pathLength="1". No transitions, no JavaScript, no infinite loops longer than the graphic.
- The canvas is 1080 wide, 1920 tall, transparent: never paint a full-frame background. Keep everything inside the
  free area you are given, at least 60 px from every edge, and never over the speaker's face.
- Fonts ONLY from: {fonts}. Text 56 px or larger (labels on a chart 40 px or larger); at most 7 words on screen.
- Colours: the reel's accent {accent}, white, near-black, and at most one more; strong contrast against the footage
  (use a plate, a soft shadow or a stroke behind text when the footage is busy).
- Enter within the first 0.4 s, hold while the idea is said, and exit in the last 0.3 s of the graphic.
why = one line on the idea of the design. Return JSON only."""

CHECK = """You are the art director checking one motion graphic laid over a vertical reel. You see three frames of
it (30%, 60% and 90% through) and the words said. Score it 1-10 against premium human edits and list every problem
a viewer would notice: text that does not read on a phone, anything cut off at an edge, covering the face, empty or
nearly invisible frames, a graphic that does not show what is said, wrong or misspelled words, clashing colours,
looking cheap or like a stock template. Problems must be concrete and fixable ("the 3 overlaps the chin; move the
counter above y=500"). An empty list only for a 9 or 10. JSON only."""


def _brief(line: str, words: list[dict], dur: float, area: str, kit: dict) -> str:
    timing = ", ".join(f"'{w['text']}' at {w['at']:.2f}s" for w in words) or "no word timings"
    return (f"The words said over this graphic ({dur:.2f} s long): \"{line}\"\nWord timings from the graphic's start: {timing}\n"
            f"Free area to design in: {area}.\nThe reel's type: big words in {kit['key']['font']}, small words in "
            f"{kit['lead']['font']}, titles in {kit['title']['font']}.\nThe first image is the footage at this moment.")


async def _render(code: MotionCode, dur: float, work: Path) -> Path | None:
    """The graphic drawn to a transparent clip, or None when the renderer could not draw it."""
    work.mkdir(parents=True, exist_ok=True)
    spec = {"id": "mg", "kind": "code", "theme": "clean", "place": "free", "dur": round(dur, 3), "box": [0, 0, W, H],
            "data": {"html": code.html, "css": code.css}, "steps": [], "lottie": None, "asset": "", "accent": ""}
    result = (await _draw([spec], work)).get("mg", {})
    if not result.get("file"):
        log.warning("Motion code did not render: %s", result.get("error"))
        return None
    return Path(result["file"])


async def _ffmpeg(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-y", *args)
    await proc.wait()


async def _frames(clip: Path, footage: Path, dur: float, work: Path) -> list[bytes]:
    """The graphic over the footage frame at each of ``LOOK_AT``, as JPEGs. The graphic's frame is taken out first:
    overlaying a seeked clip on a still in one pass kept only the still."""
    out = []
    for n, share in enumerate(LOOK_AT):
        layer, frame = work / f"layer{n}.png", work / f"look{n}.jpg"
        await _ffmpeg("-ss", f"{dur * share:.3f}", "-i", str(clip), "-frames:v", "1", str(layer))
        if not layer.exists():
            continue
        await _ffmpeg("-i", str(footage), "-i", str(layer), "-filter_complex",
                      f"[0]scale={W}:{H}[bg];[bg][1]overlay=format=auto,scale=540:-2", "-frames:v", "1", "-q:v", "4", str(frame))
        if frame.exists():
            out.append(frame.read_bytes())
    return out


def free_area(faces: list[tuple[int, int, int, int]]) -> str:
    """Where a graphic may go on a 1080x1920 frame, in words the designer can use: the bands above and below the
    (padded) faces, with their pixel bounds."""
    if not faces:
        return "anywhere on the frame; nobody's face is on screen"
    top, bottom = min(f[1] for f in faces), max(f[3] for f in faces)
    left, right = min(f[0] for f in faces), max(f[2] for f in faces)
    bands = []
    if top - 60 >= 320:
        bands.append(f"above the face: y 60-{top - 20} (full width)")
    if H - 60 - bottom >= 320:
        bands.append(f"below the face: y {bottom + 20}-{H - 60} (full width; footage there is the body or the table)")
    sides = [f"left of the face: x 60-{left - 20}" for _ in [0] if left - 60 >= 300] + \
            [f"right of the face: x {right + 20}-{W - 60}" for _ in [0] if W - 60 - right >= 300]
    return (f"the face covers x {left}-{right}, y {top}-{bottom}; never draw over it. Free: "
            + "; ".join(bands + sides or ["only a thin margin; keep the graphic small and at an edge"])
            + ". Prefer the biggest free band and use it boldly.")


async def make(line: str, words: list[dict], dur: float, footage: Path, work: Path, kit_id: str = "", accent: str = "",
               faces: list[tuple[int, int, int, int]] | None = None) -> tuple[MotionCode, Path, int] | None:
    """A graphic designed for ``line`` over ``footage`` (a 1080x1920 frame): (code, rendered clip, score) for the best
    try, or None when no try rendered. ``words`` are {text, at} with ``at`` in seconds from the graphic's start;
    ``faces`` are padded face boxes in output pixels (layout.look)."""
    from reel_engine.ai import vision_json

    kit = typekits.catalog().get(kit_id) or next(iter(typekits.catalog().values()))
    system = SYSTEM.replace("{fonts}", ", ".join(sorted(typekits.declared_fonts()))).replace("{accent}", accent or kit["accent"])
    brief = _brief(line, words, dur, free_area(faces or []), kit)
    still = footage.read_bytes()
    best: tuple[MotionCode, Path, int] | None = None
    notes = ""
    for n in range(TRIES):
        code = await vision_json(system, brief + notes, [still], MotionCode, max_tokens=6000, step="reel_motion_code")
        try:
            code.html, code.css = clean(code.html, code.css)
        except Rejected as exc:
            notes = f"\n\nYour last code was rejected: {exc}. Write it again inside the contract."
            continue
        clip = await _render(code, dur, work / f"try{n}")
        if clip is None:
            notes = "\n\nYour last code did not render. Write simpler, valid HTML and CSS."
            continue
        looked = await vision_json(CHECK, f"Words said: \"{line}\"", await _frames(clip, footage, dur, work / f"try{n}"), Look,
                                   max_tokens=800, step="reel_motion_check")
        log.info("Motion code try %d scored %d: %s", n + 1, looked.score, "; ".join(looked.problems)[:300])
        if best is None or looked.score > best[2]:
            keep = work / f"best{n}.mov"
            shutil.copyfile(clip, keep)
            best = (code, keep, looked.score)
        if looked.score >= PASS_SCORE:
            break
        notes = (f"\n\nYour last version scored {looked.score}/10. Fix every one of these and send the whole graphic "
                 "again:\n- " + "\n- ".join(looked.problems) + f"\nYour last code was:\nHTML: {code.html}\nCSS: {code.css}")
    return best
