"""The finish pass for a Pro clip with beats: grade, zoom rhythm, graphic beats and their sounds.

Runs on the cut file (after B-roll, before captions), so every time here is a
second of the cut. Two encodes, both intermediate (the caption burn encodes
the final file):

1. grade + zoom rhythm: the theme's LUT, and a gentle punch-in on every other
   sentence where the cut shows one speaker;
2. beats: each beat rendered by ``renderer/render.mjs`` to a transparent video
   and laid over its window; a beat set behind the speaker goes under a matte
   of them (:mod:`beats.cutout`); the beats' sounds join the clip's audio.

Any failure falls back to the input file: a clip without its finish still exports.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from beats import cutout, kit
from beats.grade import lut_path
from beats.plan import BEHIND, BESIDE, CARD, CHART, COUNT_UP, CTA, FLOW, IMAGE, KEYWORD, LIST, LOGO, MAP, NAME, OBJECT, STATEMENT, UI, Beat, BeatPlan
from beats.service import beat_plan
from broll.cutaways import clip_words
from broll.renditions import Probe, probe, run
from clip_generation.hook import Hook, parse_spans, source_to_cut
from core.config import get_settings
from core.logging_config import get_logger
from motion.graphics import LayoutSpan, _band, _layout_at
from motion.service import _loads
from motion.sound import MIN_SPACING, Sound, manifest, mix_graph, sound_path
from subtitle_styling.ass_generator import TITLE_SECONDS

log = get_logger(__name__)

RENDERER = Path(__file__).resolve().parent / "renderer" / "render.mjs"
RENDER_FPS = 30
RENDER_TIMEOUT_SECONDS = 600
# Punch-in on every other sentence, only where the cut follows one speaker.
ZOOM = 1.09
ZOOM_LAYOUTS = frozenset({"follow", "follow_speaker", "single_speaker"})
SENTENCE_ENDS = (".", "?", "!", "।")
# Boxes as shares of the frame: (left, width) and the height per kind.
SIDE_MARGIN = 0.08
BOX_HEIGHT = {
    COUNT_UP: 0.2, LOGO: 0.12, NAME: 0.1, KEYWORD: 0.16, OBJECT: 0.24, CTA: 0.09,
    CHART: 0.3, UI: 0.3, MAP: 0.34, FLOW: 0.42, LIST: 0.42,
}
# Where full-frame beats keep their text: a card's middle, the band behind the head.
CARD_BOX = (0.08, 0.2, 0.84, 0.6)
BEHIND_BOX = (0.03, 0.1, 0.94, 0.3)
IMAGE_CAPTION_BOX = (0.08, 0.58, 0.84, 0.2)
MONEY = ("$", "₹", "€", "£", "¥")


@dataclass
class Placed:
    """A beat on the cut's timeline with its box in pixels."""

    beat: Beat
    start: float
    end: float
    steps: list[float]
    place: str
    box: tuple[int, int, int, int]
    behind: bool = False
    matte: str = ""
    file: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@asynccontextmanager
async def with_finish(video_path: str, clip: Any, hook: Hook | None, ratio: str = "9:16") -> AsyncIterator[str]:
    """The cut to caption: finished when the clip has beats, else ``video_path`` itself."""
    plan = beat_plan(clip)
    if plan is None:
        yield video_path
        return
    with tempfile.TemporaryDirectory() as workdir:
        try:
            path = await finish(video_path, clip, hook, plan, ratio, Path(workdir))
        except Exception as exc:
            log.warning("Finish pass failed for clip %s, exporting without beats: %s", clip.id, exc)
            path = video_path
        yield path


async def finish(video_path: str, clip: Any, hook: Hook | None, plan: BeatPlan, ratio: str, workdir: Path) -> str:
    info = await probe(video_path)
    layouts = _layouts(clip, ratio)
    spans = parse_spans(clip.edit_spans)
    graded = str(workdir / "graded.mp4")
    await run(_grade_cmd(video_path, graded, plan.theme, _zoom_windows(clip, hook, spans, layouts, info), info))

    placed = [p for p in (_place(beat, clip, hook, spans, layouts, info) for beat in plan.beats) if p is not None]
    if not placed:
        return graded
    for index, item in enumerate(placed):
        if item.behind:
            matte = str(workdir / f"matte{index}.mkv")
            if await cutout.matte_video(graded, item.start, item.end, info.width, info.height, RENDER_FPS, matte):
                item.matte = matte
            else:
                item.behind = False
                item.place, item.box = _fit(item.beat.kind, BESIDE, layouts, item.start, info)
    await _render(placed, plan.theme, info, workdir)
    drawn = [item for item in placed if item.file]
    if not drawn:
        return graded
    output = str(workdir / "finished.mp4")
    await run(_compose_cmd(graded, drawn, _sounds(drawn), info, output, await _has_audio(graded)))
    log.info("Finish applied: clip=%s theme=%s beats=%d", clip.id, plan.theme, len(drawn))
    return output


def caption_quiet(clip: Any, hook: Hook | None) -> list[tuple[float, float]]:
    """Seconds of the cut where the clip's beats hold the frame and captions should step aside."""
    plan = beat_plan(clip)
    if plan is None:
        return []
    spans = parse_spans(clip.edit_spans)
    quiet = []
    for beat in plan.beats:
        if not beat.quiets_captions:
            continue
        start = source_to_cut(beat.start, clip.start_time, clip.end_time, hook, spans)
        end = source_to_cut(beat.end, clip.start_time, clip.end_time, hook, spans)
        if start is not None and end is not None:
            quiet.append((start, end))
    return quiet


# --- timing and placement ---------------------------------------------------------------------------


def _layouts(clip: Any, ratio: str) -> list[LayoutSpan]:
    formats = _loads(clip.output_formats)
    frames = (formats.get(ratio) or {}).get("frames") if isinstance(formats.get(ratio), dict) else None
    return [LayoutSpan.from_stored(item) for item in frames or [] if isinstance(item, dict) and {"start", "end", "kind"} <= item.keys()]


def _place(beat: Beat, clip: Any, hook: Hook | None, spans: list | None, layouts: list[LayoutSpan], info: Probe) -> Placed | None:
    start = source_to_cut(beat.start, clip.start_time, clip.end_time, hook, spans)
    end = source_to_cut(beat.end, clip.start_time, clip.end_time, hook, spans)
    steps = [source_to_cut(t, clip.start_time, clip.end_time, hook, spans) for t in beat.steps]
    if start is None or end is None or end - start < 0.5 or any(t is None for t in steps):
        return None  # Part of it was cut out: a half-shown graphic is worse than none.
    place = CARD if beat.kind in (STATEMENT, IMAGE) else beat.place
    if place == BEHIND and not cutout.available():
        place = BESIDE
    place, box = _fit(beat.kind, place, layouts, start, info)
    return Placed(beat, start, end, [t - start for t in steps], place, box, behind=place == BEHIND)


def _fit(kind: str, place: str, layouts: list[LayoutSpan], start: float, info: Probe) -> tuple[str, tuple[int, int, int, int]]:
    """``place`` and its box, or a card when the frame has no clear room for it."""
    box = _box(kind, place, layouts, start, info)
    return (place, box) if box is not None else (CARD, _box(kind, CARD, layouts, start, info))


def _box(kind: str, place: str, layouts: list[LayoutSpan], start: float, info: Probe) -> tuple[int, int, int, int] | None:
    W, H = info.width, info.height
    if place == CARD:
        x, y, w, h = IMAGE_CAPTION_BOX if kind == IMAGE else CARD_BOX
        return round(x * W), round(y * H), round(w * W), round(h * H)
    if place == BEHIND:
        x, y, w, h = BEHIND_BOX
        return round(x * W), round(y * H), round(w * W), round(h * H)
    height = round(BOX_HEIGHT.get(kind, 0.2) * H)
    top = _band(_layout_at(layouts, start), H, height, start < TITLE_SECONDS, SIDE_MARGIN, 1 - SIDE_MARGIN)
    if top is None:
        return None
    return round(SIDE_MARGIN * W), round(top), round((1 - 2 * SIDE_MARGIN) * W), height


def _zoom_windows(clip: Any, hook: Hook | None, spans: list | None, layouts: list[LayoutSpan], info: Probe) -> list[tuple[float, float]]:
    """Cut-second windows (every other sentence) that get the punch-in."""
    if not layouts or info.height <= info.width:
        return []
    director = _loads(clip.analysis_json).get("clip") or {}
    punched = {float(b.get("t", -1)) for b in director.get("beats") or [] if isinstance(b, dict) and b.get("fx") == "punch_in"}
    sentences: list[tuple[float, float]] = []
    words = clip_words(clip).words
    first = None
    for word in words:
        first = float(word["start"]) if first is None else first
        if str(word["word"]).strip().endswith(SENTENCE_ENDS):
            sentences.append((first, float(word["end"])))
            first = None
    windows = []
    for index, (start, end) in enumerate(sentences):
        if index % 2 == 0 or any(start <= t <= end for t in punched):
            continue
        a = source_to_cut(start, clip.start_time, clip.end_time, hook, spans)
        b = source_to_cut(end, clip.start_time, clip.end_time, hook, spans)
        if a is None or b is None or b - a < 0.8:
            continue
        if all(_layout_at(layouts, t).kind in ZOOM_LAYOUTS for t in (a, (a + b) / 2, b - 0.05)):
            windows.append((round(a, 3), round(b, 3)))
    return windows


# --- FFmpeg ---------------------------------------------------------------------------------------


def _grade_cmd(src: str, out: str, theme: str, zooms: list[tuple[float, float]], info: Probe) -> list[str]:
    W, H = info.width, info.height
    lut = str(lut_path(theme)).replace(":", r"\:")
    chain = [f"lut3d=file='{lut}'"]
    if zooms:
        # zoompan keeps one output size (scale with eval=frame would change it mid-stream);
        # one output frame per input frame, framed a little above centre to keep the face.
        z = "+".join(f"between(in_time,{a},{b})" for a, b in zooms)
        chain.append(
            f"zoompan=z='1+{ZOOM - 1:.3f}*min(1,{z})':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*0.35'"
            f":d=1:s={W}x{H}:fps={info.fps or RENDER_FPS:.3f}"
        )
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", src,
        "-vf", ",".join(chain), "-map", "0:v", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "copy", out,
    ]


async def _has_audio(path: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return bool(stdout.strip())


def _compose_cmd(src: str, drawn: list[Placed], sounds: list[Sound], info: Probe, out: str, has_audio: bool = True) -> list[str]:
    behind = [item for item in drawn if item.behind and item.matte]
    inputs = [src, *(item.file for item in drawn), *(item.matte for item in behind)]
    chains = [f"[0:v]split={1 + len(behind)}[base]" + "".join(f"[p{j}]" for j in range(len(behind)))]
    current = "base"
    matte_index = {id(item): (1 + len(drawn) + j, j) for j, item in enumerate(behind)}
    for index, item in enumerate(drawn, start=1):
        s, e = item.start, item.end
        chains.append(f"[{index}:v]format=rgba,setpts=PTS-STARTPTS+{s:.3f}/TB[o{index}]")
        chains.append(f"[{current}][o{index}]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})':eof_action=pass[v{index}]")
        current = f"v{index}"
        if id(item) in matte_index:
            m, j = matte_index[id(item)]
            chains.append(f"[p{j}]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS,format=rgba[pt{j}]")
            chains.append(f"[{m}:v]format=gray,setpts=PTS-STARTPTS[mm{j}]")
            chains.append(f"[pt{j}][mm{j}]alphamerge,setpts=PTS+{s:.3f}/TB[pp{j}]")
            chains.append(f"[{current}][pp{j}]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})':eof_action=pass[vp{j}]")
            current = f"vp{j}"
    audio = ["-map", "0:a?", "-c:a", "copy"]
    if sounds:
        base = "0:a"
        if not has_audio:
            chains.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={info.duration:.3f}[silence]")
            base = "silence"
        chains += mix_graph(sounds, base, len(inputs), out="mixed")
        audio = ["-map", "[mixed]", "-c:a", "aac", "-b:a", "192k"]
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        *[arg for path in inputs for arg in ("-i", path)],
        *[arg for sound in sounds for arg in ("-i", sound_path(sound.name))],
        "-filter_complex", ";".join(chains), "-map", f"[{current}]", *audio,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-pix_fmt", "yuv420p", "-t", f"{info.duration:.3f}", out,
    ]


# --- rendering and sounds --------------------------------------------------------------------------


async def _render(placed: list[Placed], theme: str, info: Probe, workdir: Path) -> None:
    beats = []
    for index, item in enumerate(placed):
        data = dict(item.beat.data)
        asset = kit.kit_dir() / item.beat.asset if item.beat.asset else None
        if item.beat.kind == MAP and asset and asset.is_file():
            data["svg"] = asset.read_text(encoding="utf-8")
        beats.append({
            "id": f"b{index}", "kind": item.beat.kind, "theme": theme, "place": item.place, "dur": round(item.end - item.start, 3),
            "box": list(item.box), "data": data, "steps": [round(t, 3) for t in item.steps],
            "asset": asset.resolve().as_uri() if asset and asset.is_file() else "",
        })
    spec = workdir / "beats.json"
    spec.write_text(json.dumps({"W": info.width, "H": info.height, "fps": RENDER_FPS, "beats": beats}), encoding="utf-8")
    env = {**os.environ}
    chrome = (getattr(get_settings(), "CHROME_PATH", "") or "").strip()
    if chrome:
        env["CHROME_PATH"] = chrome
    proc = await asyncio.create_subprocess_exec(
        "node", str(RENDERER), str(spec), str(workdir), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), RENDER_TIMEOUT_SECONDS)
    except TimeoutError:
        proc.kill()
        raise RuntimeError("beat renderer timed out")
    if proc.returncode != 0:
        raise RuntimeError(f"beat renderer failed: {stderr.decode('utf-8', 'ignore')[-400:]}")
    for entry in json.loads((workdir / "rendered.json").read_text(encoding="utf-8")):
        index = int(entry["id"][1:])
        if entry.get("file"):
            placed[index].file = entry["file"]
        else:
            log.warning("Beat %s (%s) did not render: %s", entry["id"], placed[index].beat.kind, entry.get("error"))


def _sounds(drawn: list[Placed]) -> list[Sound]:
    """One sound per visual event, on its frame, spaced so none smear together."""
    sounds: list[Sound] = []
    for item in drawn:
        s, kind = item.start, item.beat.kind
        if kind == COUNT_UP:
            money = str(item.beat.data.get("prefix", "")).strip() in MONEY
            sounds += [Sound("tick", s + 0.05), Sound("cash" if money else "ding", s + 1.0)]
        elif kind in (LIST, FLOW, UI):
            sounds.append(Sound("whoosh_short", s + 0.03))
            sounds += [Sound("click", s + step + 0.05) for step in item.steps]
        elif kind in (LOGO, NAME, OBJECT):
            sounds.append(Sound("pop", s + 0.04))
        elif kind == KEYWORD:
            sounds.append(Sound("boom" if item.behind else "whoosh_short", s + 0.05))
        elif kind in (STATEMENT, IMAGE):
            sounds.append(Sound("whoosh", s + 0.05))
        elif kind == CHART:
            sounds += [Sound("riser", s + 1.3), Sound("ding", s + 1.35)]
        elif kind == CTA:
            sounds += [Sound("pop", s + 0.03), Sound("ding", s + 0.3)]
        elif kind == MAP:
            sounds += [Sound("whoosh_short", s + 0.05), Sound("pop", s + 1.0)]
    spaced: list[Sound] = []
    for sound in sorted(sounds, key=lambda x: x.at):
        if sound.name in manifest() and (not spaced or sound.at - spaced[-1].at >= MIN_SPACING):
            spaced.append(sound)
    return spaced
