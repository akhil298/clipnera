"""Render: the Edit Plan becomes a finished reel.

1. Picture: every video item is cut from its source, sped or slowed (motion-interpolated slow motion),
   framed 9:16 on the face track, zoomed (push, pull or punch with a short shake), white-balanced,
   exposure-matched, steadied when shaky, cleaned when dark, graded, with light grain and vignette.
2. Graphics: every graphic and caption is drawn by the beats renderer to a transparent clip; words behind
   the person go under a matte of them.
3. Sound: the kept voice (separated from any music under it), the bed or score ducked under the voice,
   every sound effect on its frame, mixed to -14 LUFS.
4. Compose and encode once for delivery (H.264, fast start).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import numpy as np

from beats import cutout
from beats.compose import RENDERER, Placed, _behind_band, _compose_cmd
from beats.grade import grade_path
from beats.plan import Beat
from broll.renditions import probe as probe_av
from core.config import get_settings
from core.logging_config import get_logger
from reel_engine.media import FPS, H, W, mean_rgb, run
from reel_engine.plan import EditPlan, Source, VideoItem

log = get_logger(__name__)

ZOOM_CANVAS = (1350, 2400)
TARGET_LUFS = -14.0
WB_LIMIT = (0.88, 1.12)
GAMMA_LIMIT = (0.82, 1.22)
EXPOSURE_FLOOR = 0.46
SHAKY_MOTION = 25.0
# Framing: the face fills this share of the frame's height (tighter on punch-ins), the window is never shorter
# than MIN_WINDOW of the source, and the source is never upscaled more than MAX_UPSCALE.
FACE_SHARE, FACE_SHARE_TIGHT = 0.2, 0.26
MIN_WINDOW = 0.4
MAX_UPSCALE = 4.0
PARALLEL_SEGMENTS = 3
# Graphics whose parts land on given seconds (``steps``); others may use a ``steps`` field of their own (progress labels).
TIMED_KINDS = {"list", "flow", "ui"}


# ------------------------------------------------------------------ picture

def white_balance(source: Source) -> str:
    """Grey-world gains for the whole source, clamped: removes a colour cast before the grade."""
    if source.kind != "video" or source.duration <= 0:
        return ""
    rgb = mean_rgb(source.path, [source.duration * k / 6 for k in range(1, 6)])
    gains = np.clip(rgb.mean() / np.maximum(rgb, 1), *WB_LIMIT)
    return f"colorchannelmixer=rr={gains[0]:.3f}:gg={gains[1]:.3f}:bb={gains[2]:.3f}"


def exposure(source: Source, item: VideoItem, target: float) -> float:
    level = float(mean_rgb(source.path, [(item.t0 + item.t1) / 2]).mean() / 255)
    if not (0.05 < target < 0.95) or level <= 0.03:
        return 1.0
    return float(np.clip(np.log(level) / np.log(target), *GAMMA_LIMIT))


def framing(source: Source, item: VideoItem, track: list[list[float]]) -> tuple[str | None, float]:
    """A 9:16 window framed on the person, as (crop filter, upscale factor); (None, 1) when the source needs none.

    With a face: sized so the face fills about a fifth of the frame (medium close-up), tighter on punch-ins,
    never upscaled past MAX_UPSCALE, face in the upper third, following the face sideways over the item.
    Without one: the full height, centred.
    """
    aspect = source.width / max(1, source.height)
    points = [p for p in track if item.t0 - 1.0 <= p[0] <= item.t1 + 1.0]
    if not points and track:
        nearest = min(track, key=lambda p: abs(p[0] - (item.t0 + item.t1) / 2))
        points = [nearest] if abs(nearest[0] - item.t0) < 6 else []
    if aspect <= 9 / 16 + 0.01 and not points:
        return None, 1.0
    height = 1.0
    top = 0.0
    if points:
        face_w = float(np.median([p[3] for p in points]))
        face_y = float(np.median([p[2] for p in points]))
        face_h = face_w * aspect * 1.3  # the box is wider than the face is tall; as a share of the frame's height
        share = FACE_SHARE_TIGHT if item.zoom == "punch" else FACE_SHARE
        least = (W / MAX_UPSCALE) * 16 / 9 / max(1, source.height)  # the shortest window still sharp enough
        height = float(np.clip(face_h / share, max(least, MIN_WINDOW), 1.0))
        height = min(height, aspect * 16 / 9)  # the window can't be wider than the source
        top = float(np.clip(face_y - 0.32 * height, 0.0, 1.0 - height))
    width = height * 9 / 16 / aspect
    centres = [p[1] for p in points] or [0.5]
    anchor = float(np.median(centres))
    keys = sorted({(round(max(0.0, (p[0] - item.t0) / item.speed), 2), 0.7 * anchor + 0.3 * p[1]) for p in points}) or [(0.0, anchor)]
    left = lambda c: min(max(c - width / 2, 0.0), max(0.0, 1.0 - width))  # noqa: E731
    expr = f"{left(keys[-1][1]):.4f}"
    for (t_a, c_a), (t_b, c_b) in reversed(list(zip(keys, keys[1:]))):
        a, b = left(c_a), left(c_b)
        expr = f"if(lt(t,{t_b}),{a:.4f}+({b - a:.4f})*(t-{t_a})/{max(0.01, t_b - t_a):.2f},{expr})"
    upscale = W / max(1.0, width * source.width)
    return f"crop=iw*{width:.4f}:ih*{height:.4f}:'({expr})*iw':ih*{top:.4f}", upscale


def zoom_expr(kind: str, frames: int) -> str:
    n = max(frames - 1, 1)
    return {"in": f"1.0+0.07*on/{n}", "out": f"1.07-0.07*on/{n}", "punch": "1.04+0.15*exp(-on/4)", "hold": "1.0"}[kind]


def shake(kind: str, rate: float) -> str:
    return f"+28*exp(-on/5)*sin(on*{rate})" if kind == "punch" else ""


def segment_cmd(source: Source, item: VideoItem, track: list[list[float]], wb: str, gamma: float, grade: Path, shaky: bool,
                dark: bool, out: Path) -> list[str]:
    length = item.out1 - item.out0
    count = max(1, round(length * FPS))
    cw, ch = ZOOM_CANVAS
    chain = []
    if source.kind == "image":
        inputs = ["-loop", "1", "-t", f"{length + 0.2:.3f}", "-i", source.path]
        chain.append(f"scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch}")
    else:
        inputs = ["-ss", f"{item.t0:.3f}", "-t", f"{item.t1 - item.t0 + 0.12:.3f}", "-i", source.path]
        chain.append(f"setpts=(PTS-STARTPTS)/{item.speed:.4f}")
        if item.speed < 0.9:
            chain.append(f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
        if shaky:
            chain.append("deshake")
        crop, upscale = framing(source, item, track)
        if crop:
            chain.append(crop)
        chain.append(f"scale={cw}:{ch}:flags=lanczos:force_original_aspect_ratio=increase,crop={cw}:{ch}")
        if upscale > 2.0:
            chain.append("unsharp=5:5:0.6:5:5:0.0")
    chain.append(f"fps={FPS}")
    chain.append(f"zoompan=z='{zoom_expr(item.zoom, count)}':x='iw/2-(iw/zoom/2){shake(item.zoom, 2.3)}'"
                 f":y='ih/2-(ih/zoom/2){shake(item.zoom, 3.1)}':d=1:s={W}x{H}:fps={FPS}")
    if dark:
        chain.append("hqdn3d=2:1.5:3:3")
    if wb:
        chain.append(wb)
    if abs(gamma - 1.0) > 0.02:
        chain.append(f"eq=gamma={gamma:.3f}")
    chain += [f"lut3d=file='{str(grade).replace(':', chr(92) + ':')}'", "eq=contrast=1.04:saturation=1.1", "vignette=PI/9",
              "noise=alls=4:allf=t", "format=yuv420p"]
    return ["ffmpeg", "-v", "error", "-y", *inputs, "-an", "-vf", ",".join(chain), "-frames:v", str(count),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", str(out)]


async def render_picture(plan: EditPlan, grade_name: str, work: Path) -> Path:
    sources = {s.index: s for s in plan.sources}
    wbs = {s.index: white_balance(s) for s in plan.sources}
    target = float(np.median([mean_rgb(sources[i.src].path, [(i.t0 + i.t1) / 2]).mean() / 255 for i in plan.video
                              if sources[i.src].kind == "video"] or [0.45]))
    # Match toward the brighter of the median and a bright floor: dim shots are lifted, bright ones kept.
    target = max(target, EXPOSURE_FLOOR)
    grade = grade_path(grade_name)
    shots = {(s.src, round(s.t0, 2)): s for s in plan.shots}
    slots = asyncio.Semaphore(PARALLEL_SEGMENTS)

    async def one(n: int, item: VideoItem) -> Path:
        source = sources[item.src]
        shot = next((s for (src, _), s in shots.items() if src == item.src and s.t0 <= item.t0 < s.t1), None)
        out = work / f"seg{n:03d}.mp4"
        cmd = segment_cmd(source, item, plan.face_track.get(str(item.src), []), wbs[item.src],
                          exposure(source, item, target) if source.kind == "video" else 1.0, grade,
                          bool(shot and shot.motion >= SHAKY_MOTION and not shot.faces), bool(shot and shot.dark), out)
        async with slots:
            await asyncio.to_thread(run, cmd)
        return out

    parts = await asyncio.gather(*(one(n, item) for n, item in enumerate(plan.video)))
    listing = work / "segments.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    cut = work / "picture.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(cut)])
    return cut


# ------------------------------------------------------------------ graphics

async def resolve_behind(plan: EditPlan, picture: Path, work: Path) -> None:
    """Words behind the person: a matte and a readable band, or drawn big in front when no full band clears them."""
    info = await probe_av(str(picture))
    for g in plan.graphics:
        if not g.behind:
            continue
        matte = work / f"matte_{g.id}.mkv"
        band = None
        box = tuple(g.box or [20, 300, 1040, 520])
        if await cutout.matte_video(str(picture), g.start, g.end, W, H, FPS, str(matte)):
            band = await _behind_band(str(matte), g.end - g.start, box, info)
        if band and band[2] >= W * 0.6:
            g.box, g.data["matte"] = list(band), str(matte)
        else:
            g.behind, g.place, g.box = False, "beside", []


def _uri(path: str) -> str:
    return Path(path).resolve().as_uri() if path and Path(path).is_file() else ""


def graphic_specs(plan: EditPlan) -> list[dict]:
    specs = []
    for g in plan.graphics:
        timed = g.kind in TIMED_KINDS
        data = {k: v for k, v in g.data.items() if k not in ("icon_query", "matte") and not (timed and k == "steps")}
        if g.kind == "map" and g.asset:
            data["svg"] = Path(g.asset.path).read_text(encoding="utf-8")
        specs.append({"id": g.id, "kind": g.kind, "theme": "clean", "place": g.place, "dur": round(g.end - g.start, 3),
                      "box": g.box, "data": data, "steps": g.data.get("steps", []) if timed else [], "asset": _uri(g.asset.path) if g.asset else "",
                      "accent": plan.brief.accent if plan.brief else "#ffb020"})
    for c in plan.captions:
        specs.append({"id": c.id, "kind": "two", "theme": "clean", "place": "beside", "dur": round(c.end - c.start, 3), "box": c.box,
                      "data": {"lead": c.lead, "text": c.keyword}, "steps": [], "asset": _uri(c.icon.path) if c.icon else "",
                      "accent": plan.brief.accent if plan.brief else "#ffb020"})
    return specs


async def render_graphics(plan: EditPlan, work: Path) -> list[Placed]:
    specs = graphic_specs(plan)
    if not specs:
        return []
    spec_file = work / "graphics.json"
    spec_file.write_text(json.dumps({"W": W, "H": H, "fps": FPS, "beats": specs}))
    env = {**os.environ}
    chrome = (getattr(get_settings(), "CHROME_PATH", "") or "").strip()
    if chrome:
        env["CHROME_PATH"] = chrome
    elif Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists():
        env["CHROME_PATH"] = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    proc = await asyncio.create_subprocess_exec("node", str(RENDERER), str(spec_file), str(work), env=env,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"graphics renderer failed: {err.decode('utf-8', 'ignore')[-500:]}")
    rendered = {r["id"]: r for r in json.loads((work / "rendered.json").read_text())}
    timing = {g.id: (g.start, g.end, g.data.get("matte", "")) for g in plan.graphics}
    timing.update({c.id: (c.start, c.end, "") for c in plan.captions})
    placed = []
    for spec in specs:
        entry = rendered.get(spec["id"], {})
        if not entry.get("file"):
            log.warning("Graphic %s (%s) did not render: %s", spec["id"], spec["kind"], entry.get("error"))
            continue
        start, end, matte = timing[spec["id"]]
        p = Placed(Beat(kind=spec["kind"], start=start, end=end), start, end, [], spec["place"], tuple(spec["box"]), file=entry["file"])
        p.matte, p.behind = matte, bool(matte)
        placed.append(p)
    return placed


# ------------------------------------------------------------------ compose + encode

async def compose(plan: EditPlan, picture: Path, placed: list[Placed], mix: Path, work: Path, out: Path) -> Path:
    info = await probe_av(str(picture))
    drawn = work / "drawn.mp4"
    if placed:
        await asyncio.to_thread(run, _compose_cmd(str(picture), placed, [], info, str(drawn), False))
    else:
        drawn = picture
    run(["ffmpeg", "-v", "error", "-y", "-i", str(drawn), "-i", str(mix), "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)])
    return out
