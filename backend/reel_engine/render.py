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
import hashlib
import json
import os
import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np

from beats import cutout
from beats.compose import RENDERER, Placed, _behind_band, _compose_cmd
from beats.grade import grade_path
from beats.plan import Beat
from broll.renditions import probe as probe_av
from core.config import get_settings
from core.logging_config import get_logger
from reel_engine import effects, typekits
from reel_engine.media import FPS, INTERMEDIATE_PRESET, H, W, mean_rgb, run
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
# Work side by side only as far as the machine has cores (the worker has two).
PARALLEL_SEGMENTS = min(3, os.cpu_count() or 1)
GRAPHICS_TIMEOUT = 300
# Pages the renderer draws on side by side, and the time each frame may take on a busy machine (shared by the pages).
RENDER_WORKERS, FRAME_SECONDS = min(3, os.cpu_count() or 1), 0.5
# Graphics whose parts land on given seconds (``steps``); others may use a ``steps`` field of their own (progress labels).
TIMED_KINDS = {"list", "flow", "ui"}


# ------------------------------------------------------------------ picture

def _grey_world(rgb: np.ndarray) -> np.ndarray:
    return np.clip(rgb.mean() / np.maximum(rgb, 1), *WB_LIMIT)


@lru_cache(maxsize=16)
def _source_gains(path: str, duration: float) -> np.ndarray:
    return _grey_world(mean_rgb(path, [duration * k / 6 for k in range(1, 6)]))


def white_balance(source: Source, item: VideoItem | None = None) -> str:
    """Grey-world gains, clamped: removes a colour cast before the grade. With ``item``, the source's gains are blended
    half and half with the shot's own, so a shot that drifts warmer or cooler (a lamp, a window) matches its neighbours
    without flattening the source's look."""
    if source.kind != "video" or source.duration <= 0:
        return ""
    gains = _source_gains(source.path, source.duration)
    if item is not None:
        gains = np.clip((gains + _grey_world(mean_rgb(source.path, [item.t0 + (item.t1 - item.t0) * k for k in (0.25, 0.75)]))) / 2,
                        *WB_LIMIT)
    return f"colorchannelmixer=rr={gains[0]:.3f}:gg={gains[1]:.3f}:bb={gains[2]:.3f}"


def exposure(source: Source, item: VideoItem, target: float) -> float:
    level = float(mean_rgb(source.path, [(item.t0 + item.t1) / 2]).mean() / 255)
    if not (0.05 < target < 0.95) or level <= 0.03:
        return 1.0
    return float(np.clip(np.log(level) / np.log(target), *GAMMA_LIMIT))


PERSON_GAP = 0.12        # faces further apart than this (share of the width) are different people
TALK_MIN = 0.012         # mouth motion under this is someone listening
SPLIT_MIN_SECONDS = 2.0  # a split screen only for an exchange long enough to read
SPLIT_FACE_SHARE = 0.34  # a face's height as a share of its half of a split screen
NEAREST_FACE = 1.5  # seconds a face seen outside a shot still frames it


def people(rows: list[list[float]]) -> list[dict]:
    """Faces grouped into people by where they sit across the frame: rows, how often seen, size, how much they talk."""
    if not rows:
        return []
    times = sorted({r[0] for r in rows})
    groups: list[list[list[float]]] = []
    for row in sorted(rows, key=lambda r: r[1]):
        if groups and row[1] - groups[-1][-1][1] <= PERSON_GAP:
            groups[-1].append(row)
        else:
            groups.append([row])
    out = []
    for g in groups:
        seen = {r[0] for r in g}
        out.append({"rows": sorted(g, key=lambda r: r[0]), "presence": len(seen) / len(times),
                    "size": float(np.median([r[3] for r in g])), "talk": float(np.mean([r[5] if len(r) > 5 else 0.0 for r in g])),
                    "x": float(np.median([r[1] for r in g]))})
    return sorted(out, key=lambda p: -p["presence"])


def pick_people(found: list[dict], seconds: float) -> tuple[dict | None, tuple[dict, dict] | None]:
    """The person to frame (the one talking, else the most present and biggest) or two for a split screen."""
    candidates = [p for p in found if p["presence"] >= 0.3] or found[:1]
    if not candidates:
        return None, None
    loudest = max(p["talk"] for p in candidates)
    if len(candidates) >= 2 and seconds >= SPLIT_MIN_SECONDS and loudest >= TALK_MIN:
        a, b = sorted(candidates, key=lambda p: -p["talk"])[:2]
        if a["presence"] >= 0.6 and b["presence"] >= 0.6 and b["talk"] >= 0.45 * a["talk"] and max(a["size"], b["size"]) < 0.3:
            return None, tuple(sorted((a, b), key=lambda p: p["x"]))
    if loudest >= TALK_MIN:
        return max(candidates, key=lambda p: p["talk"] * (0.5 + p["presence"])), None
    return max(candidates, key=lambda p: p["presence"] * (0.5 + p["size"])), None


SPLIT_INSIDE = 0.85  # share of a person's sightings whose face must sit inside their half, or no split


def _split(source: Source, pair: tuple[dict, dict]) -> tuple[str, float] | None:
    """Two people stacked, each in a half of the frame (9:8), sized on their own face; None when a half would lose its
    face for much of the shot (someone leaning out, a face found only now and then): cut to the talker instead."""
    aspect = source.width / max(1, source.height)
    parts, widths = [], []
    for person in pair:
        rows = person["rows"]
        face_h = float(np.median([r[4] if len(r) > 4 else r[3] * aspect * 1.3 for r in rows]))
        face_y = float(np.median([r[2] for r in rows]))
        height = float(np.clip(face_h / SPLIT_FACE_SHARE, MIN_WINDOW * 0.6, 1.0))
        width = height * (9 / 8) / aspect
        if width > 1.0:
            width, height = 1.0, aspect * 8 / 9
        top = float(np.clip(face_y - 0.42 * height, 0.0, 1.0 - height))
        left = float(np.clip(person["x"] - width / 2, 0.0, 1.0 - width))
        inside = sum(1 for r in rows if left + 0.3 * r[3] <= r[1] <= left + width - 0.3 * r[3] and top <= r[2] <= top + height)
        if inside < SPLIT_INSIDE * len(rows):
            return None
        parts.append(f"crop=iw*{width:.4f}:ih*{height:.4f}:iw*{left:.4f}:ih*{top:.4f},scale={W}:{H // 2}")
        widths.append(width)
    upscale = W / max(1.0, min(widths) * source.width)
    return f"split[sa][sb];[sa]{parts[0]}[ta];[sb]{parts[1]}[tb];[ta][tb]vstack", upscale


def framing(source: Source, item: VideoItem, track: list[list[float]], focus: list[list[float]] | None = None,
            inside: list[float] | None = None) -> tuple[str | None, float]:
    """A 9:16 window framed on the right subject, as (crop filter, upscale factor); (None, 1) when the source needs none.

    The subject is the person talking (followed sideways over the item; the camera stays with them rather than
    hopping to whoever is biggest each second), both people stacked when two trade lines in a wide two-shot, or,
    when nobody is on screen, the window holding the most detail and movement (``focus``) instead of the middle.
    Sized so the face fills about a fifth of the frame, tighter on punch-ins, never upscaled past MAX_UPSCALE; kept
    inside ``inside`` (rows, as shares of the height) when the footage's own subtitles run along an edge.
    """
    aspect = source.width / max(1, source.height)
    rows = [r for r in track if item.t0 - 0.5 <= r[0] <= item.t1 + 0.5]
    if not rows and track:
        nearest = min(track, key=lambda p: abs(p[0] - (item.t0 + item.t1) / 2))
        # A face seen just before the shot still frames it; one from seconds away (someone stood up) would frame the wall.
        rows = [r for r in track if r[0] == nearest[0]] if abs(nearest[0] - item.t0) < NEAREST_FACE else []
    found = people(rows)
    if aspect <= 9 / 16 + 0.01 and not found:
        return None, 1.0
    chosen, pair = pick_people(found, (item.t1 - item.t0) / item.speed)
    if pair:
        split = _split(source, pair)
        if split:
            return split
        chosen = max(pair, key=lambda p: p["talk"])
    points = [[r[0], r[1], r[2], r[3]] for r in chosen["rows"]] if chosen else []
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
    else:
        # Nobody on screen: follow what matters (detail and movement), smoothed so the window glides.
        near = [f for f in (focus or []) if item.t0 - 0.5 <= f[0] <= item.t1 + 0.5]
        points = [[f[0], float(np.median([g[1] for g in near[max(0, k - 2):k + 3]])), 0.5, 0.0] for k, f in enumerate(near)]
    if inside:
        height = min(height, inside[1] - inside[0])
        top = float(np.clip(top, inside[0], inside[1] - height))
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
    """No camera shake: on a talking reel it reads as a glitch, so punch-ins are a clean zoom."""
    return ""


def segment_cmd(source: Source, item: VideoItem, track: list[list[float]], wb: str, gamma: float, grade: Path, shaky: bool,
                dark: bool, out: Path, focus: list[list[float]] | None = None, fit: bool = False,
                rows: list[float] | None = None) -> list[str]:
    length = item.out1 - item.out0
    count = max(1, round(length * FPS))
    cw, ch = ZOOM_CANVAS
    colour = (["hqdn3d=2:1.5:3:3"] if dark else []) + ([wb] if wb else []) + ([f"eq=gamma={gamma:.3f}"] if abs(gamma - 1.0) > 0.02 else [])
    colour += [f"lut3d=file='{str(grade).replace(':', chr(92) + ':')}'", "eq=contrast=1.04:saturation=1.1"]
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
        crop, upscale = (None, 0.0) if fit else framing(source, item, track, focus, rows)
        if fit:
            # The whole frame across the middle over a blurred copy of itself: the footage's own text stays whole.
            chain.append(f"split[bg][fg];[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=12:2,"
                         f"eq=brightness=-0.06,scale={cw}:{ch}[b];[fg]scale={cw}:-2[f];[b][f]overlay=0:(H-h)/2")
        if crop:
            chain.append(crop)
        if upscale >= 1.0:
            # The grade costs per pixel: on the window before it is scaled up it does a third of the work (3x faster).
            chain += colour
            colour = []
        if not fit:
            chain.append(f"scale={cw}:{ch}:flags=lanczos:force_original_aspect_ratio=increase,crop={cw}:{ch}")
        if upscale > 2.0:
            chain.append("unsharp=5:5:0.6:5:5:0.0")
    chain.append(f"fps={FPS}")
    # A zoom would cut the sides of a fitted frame, and the text there with them.
    chain.append(f"zoompan=z='{zoom_expr('hold' if fit else item.zoom, count)}':x='iw/2-(iw/zoom/2){shake(item.zoom, 2.3)}'"
                 f":y='ih/2-(ih/zoom/2){shake(item.zoom, 3.1)}':d=1:s={W}x{H}:fps={FPS}")
    chain += [*colour, "vignette=PI/9", "noise=alls=4:allf=t", "format=yuv420p"]
    return ["ffmpeg", "-v", "error", "-y", *inputs, "-an", "-vf", ",".join(chain), "-frames:v", str(count),
            "-c:v", "libx264", "-preset", INTERMEDIATE_PRESET, "-crf", "17", str(out)]


async def render_picture(plan: EditPlan, grade_name: str, work: Path) -> Path:
    sources = {s.index: s for s in plan.sources}
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
        cmd = segment_cmd(source, item, plan.face_track.get(str(item.src), []), white_balance(source, item),
                          exposure(source, item, target) if source.kind == "video" else 1.0, grade,
                          bool(shot and shot.motion >= SHAKY_MOTION and not shot.faces), bool(shot and shot.dark), out,
                          plan.focus_track.get(str(item.src), []), fit=bool(plan.brief and plan.brief.fit),
                          rows=plan.brief.text_free.get(str(item.src)) if plan.brief else None)
        async with slots:
            await asyncio.to_thread(run, cmd)
        return out

    parts = await asyncio.gather(*(one(n, item) for n, item in enumerate(plan.video)))
    listing = work / "segments.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    cut = work / "picture.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(cut)])
    return cut


async def render_inserts(plan: EditPlan, picture: Path, grade_name: str, work: Path) -> Path:
    """Full-frame cutaways laid over the picture (the voice carries on underneath)."""
    from reel_engine.inserts import cutaway_cmd, overlay_cmd

    if not plan.inserts:
        return picture
    grade = grade_path(grade_name)
    cuts = []
    for item in plan.inserts:
        out = work / f"insert_{item.id}.mp4"
        try:
            await asyncio.to_thread(run, cutaway_cmd(item, out, grade, FPS, W, H))
            cuts.append((item, out))
        except Exception as exc:  # an unreadable insert is left out; the speaker stays on screen
            log.warning("Insert %s skipped: %s", item.id, exc)
    if not cuts:
        return picture
    out = work / "picture_inserts.mp4"
    await asyncio.to_thread(run, overlay_cmd(picture, cuts, out))
    return out


# ------------------------------------------------------------------ graphics

async def resolve_behind(plan: EditPlan, picture: Path, work: Path) -> None:
    """Words behind the person: a matte and a readable band, or drawn big in front when no full band clears them."""
    info = await probe_av(str(picture))
    dropped = set()
    for g in plan.graphics:
        if not g.behind:
            continue
        matte = work / f"matte_{g.id}.mkv"
        if g.kind == "effect":
            if await cutout.matte_video(str(picture), g.start, g.end, W, H, FPS, str(matte)):
                g.data["matte"] = str(matte)
            else:
                dropped.add(g.id)
            continue
        band = None
        box = tuple(g.box or [20, 300, 1040, 520])
        if await cutout.matte_video(str(picture), g.start, g.end, W, H, FPS, str(matte)):
            band = await _behind_band(str(matte), g.end - g.start, box, info)
        if band and band[2] >= W * 0.6:
            g.box, g.data["matte"] = list(band), str(matte)
        else:
            g.behind, g.place, g.box = False, "beside", []
    if dropped:
        # Without the speaker's matte an effect meant to sit behind them goes, with its front half.
        gone = {g.data.get("effect") + str(g.start) for g in plan.graphics if g.id in dropped}
        plan.graphics = [g for g in plan.graphics if not (g.kind == "effect" and g.data.get("effect") + str(g.start) in gone)]
        log.info("Effects dropped without a speaker matte: %s", ", ".join(sorted(gone)))


def _uri(path: str) -> str:
    return Path(path).resolve().as_uri() if path and Path(path).is_file() else ""


TITLE_KINDS = {"chapter", "cta", "flicker", "progress", "statement"}
# Caption looks rotated through a reel, a couple of lines each, so the words never move the same way for long.
CAPTION_LOOKS = ("pop", "slide", "stack", "pop", "punch")
LINES_PER_LOOK = 2
# Styles drawn in the brand accent; the others carry their own palette (neon magenta, comic yellow...).


def _lottie(asset) -> dict | None:
    """The animation of a Lottie asset (a motion graphic or an animated emoji), inlined for the renderer."""
    if asset and asset.path.endswith(".json") and Path(asset.path).is_file():
        return json.loads(Path(asset.path).read_text(encoding="utf-8"))
    return None


def caption_look(plan: EditPlan, n: int) -> str:
    """The opening and payoff lines punch; the rest rotate through the looks, starting where this reel's kit says."""
    c = plan.captions[n]
    if n == 0 or c.payoff:
        return "punch"
    looks = (plan.brief.caption_looks if plan.brief and plan.brief.caption_looks else None) or CAPTION_LOOKS
    first = sum(map(ord, plan.brief.type_kit if plan.brief else "")) % len(looks)
    return looks[(first + n // LINES_PER_LOOK) % len(looks)]


def _kit(plan: EditPlan, role: str) -> dict:
    """The reel's type kit for a graphic (typekits.spec); the accent is the one the brief settled on."""
    kit = typekits.spec(plan.brief.type_kit if plan.brief else "", role)
    if plan.brief and plan.brief.accent:
        kit["vars"]["--accent"] = plan.brief.accent
    return kit


def graphic_specs(plan: EditPlan) -> list[dict]:
    specs = []
    text_kit, title_kit = _kit(plan, "text"), _kit(plan, "title")
    accent = plan.brief.accent if plan.brief and plan.brief.accent else typekits.FALLBACK_ACCENT
    for g in plan.graphics:
        if g.kind == "effect":
            if effects.drawn(g):
                specs.append({"id": g.id, "kind": "effect", "theme": "clean", "kit": title_kit, "place": "effect",
                              "dur": round(g.end - g.start, 3), "box": g.box, "data": effects.spec_data(g), "steps": [], "asset": "",
                              "lottie": None, "accent": accent})
            continue
        timed = g.kind in TIMED_KINDS
        data = {k: v for k, v in g.data.items() if k not in ("icon_query", "matte") and not (timed and k == "steps")}
        if g.kind == "map" and g.asset:
            data["svg"] = Path(g.asset.path).read_text(encoding="utf-8")
        # The hook headline is read like the captions; other titles take the kit's title font.
        title = g.kind != "hook" and (g.kind in TITLE_KINDS or g.by == "finish" or g.why == "hook word")
        specs.append({"id": g.id, "kind": g.kind, "theme": "clean", "kit": title_kit if title else text_kit, "place": g.place,
                      "dur": round(g.end - g.start, 3), "box": g.box, "data": data, "steps": g.data.get("steps", []) if timed else [],
                      "lottie": _lottie(g.asset), "asset": _uri(g.asset.path) if g.asset and not g.asset.path.endswith(".json") else "",
                      "accent": accent})
    for n, c in enumerate(plan.captions):
        words = [{**w, "text": w["text"].strip(",.")} for w in c.words] or [{"text": c.lead, "key": False, "at": 0}, {"text": c.keyword, "key": True, "at": 0.1}]
        specs.append({"id": c.id, "kind": "caption", "theme": "clean", "kit": text_kit, "place": "beside", "dur": round(c.end - c.start, 3),
                      "box": c.box, "data": {"words": words, "alt": n % 3 == 2, "look": caption_look(plan, n)}, "steps": [],
                      "lottie": _lottie(c.icon), "asset": _uri(c.icon.path) if c.icon and not c.icon.path.endswith(".json") else "",
                      "accent": accent})
    return specs


def _spec_key(spec: dict) -> str:
    """What a graphic looks like (everything but its id): two passes that draw the same thing share one render."""
    return hashlib.sha1(json.dumps({k: v for k, v in spec.items() if k != "id"}, sort_keys=True).encode()).hexdigest()


async def render_graphics(plan: EditPlan, work: Path, captions_only: bool = False) -> list[Placed]:
    """Every graphic and caption drawn to a clip. Renders are kept in the reel's cache (beside the pass folders), so
    a later review pass draws only the items it changed."""
    specs = [s for s in graphic_specs(plan) if not captions_only or s["kind"] == "caption"]
    if not specs:
        return []
    cache = work.parent / "graphics_cache"
    cache.mkdir(exist_ok=True)
    keys = {s["id"]: _spec_key(s) for s in specs}
    cached = {i: str(cache / f"{k}.mov") for i, k in keys.items() if (cache / f"{k}.mov").exists()}
    rendered = {i: {"id": i, "file": f} for i, f in cached.items()}
    todo = [s for s in specs if s["id"] not in cached]
    if todo:
        rendered.update(await _draw(todo, work))
        for i, entry in rendered.items():
            if i not in cached and entry.get("file"):
                shutil.copyfile(entry["file"], cache / f"{keys[i]}.mov")
    log.info("Graphics: %d drawn, %d reused", len(todo), len(cached))
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


async def _draw(specs: list[dict], work: Path, frame_seconds: float = FRAME_SECONDS) -> dict[str, dict]:
    """The renderer run on ``specs``: {id: {"file": ..., "error": ...}}; ``frame_seconds`` is the time allowed a frame."""
    spec_file = work / "graphics.json"
    spec_file.write_text(json.dumps({"W": W, "H": H, "fps": FPS, "beats": specs}))
    env = {**os.environ, "RENDER_WORKERS": str(RENDER_WORKERS)}
    chrome = (getattr(get_settings(), "CHROME_PATH", "") or "").strip()
    if chrome:
        env["CHROME_PATH"] = chrome
    elif Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists():
        env["CHROME_PATH"] = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    proc = await asyncio.create_subprocess_exec("node", str(RENDERER), str(spec_file), str(work), env=env,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        frames = sum(s["dur"] for s in specs) * FPS
        _, err = await asyncio.wait_for(proc.communicate(), GRAPHICS_TIMEOUT + frames * frame_seconds / RENDER_WORKERS)
    except TimeoutError:
        proc.kill()
        raise RuntimeError("graphics renderer timed out")
    if proc.returncode != 0:
        raise RuntimeError(f"graphics renderer failed: {err.decode('utf-8', 'ignore')[-500:]}")
    return {r["id"]: r for r in json.loads((work / "rendered.json").read_text())}


# ------------------------------------------------------------------ compose + encode

async def compose(plan: EditPlan, picture: Path, placed: list[Placed], mix: Path, work: Path, out: Path) -> Path:
    info = await probe_av(str(picture))
    drawn = work / "drawn.mp4"
    if placed:
        await asyncio.to_thread(run, _compose_cmd(str(picture), placed, [], info, str(drawn), False))
    else:
        drawn = picture
    run(["ffmpeg", "-v", "error", "-y", "-i", str(drawn), "-i", str(mix), "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)])
    return out
