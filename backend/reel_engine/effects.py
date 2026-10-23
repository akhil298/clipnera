"""Effects: signature edits (Headline Wall, Orbit, Framebreak, Vertigo...) picked by the director from a catalog.

The catalog (data/effects.json) is the contract. It tells the director what each effect is, when to use it and
what words it needs; the director names an effect, the moment (word ids) and writes those words. This module only
checks the words against the catalog (counts, lengths, choices, how many per reel, spacing) and lays the effect
out on the speaker. The look lives in the renderer (beats/renderer/effects.js); effects that change the footage
itself (a pull-back, a zoom through a cut, a dolly zoom, the video shrinking into a frame or a phone, a frosted
panel) are rendered here, on the cut picture, before graphics are laid out.

Layers: front (over everything), behind (under the speaker's cut-out; an opaque one replaces the background),
split (one part behind the speaker, one in front), picture (the footage itself changes).
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from beats import cutout
from core.logging_config import get_logger
from reel_engine.media import FPS, H, W, run
from reel_engine.plan import EditPlan, GraphicItem, VideoItem, Word

log = get_logger(__name__)

CATALOG = Path(__file__).resolve().parent / "data" / "effects.json"
# Story graphics an effect replaces while it is up (captions, chapters, progress and the call to action stay).
YIELDING = {"two", "keyword", "tag", "list", "statement", "count_up", "chart", "flow", "name", "photocard", "flicker", "accent"}
CUT_SNAP = 1.0
ZOOM_HALF = 0.3


class DEffect(BaseModel):
    """What the director writes for one effect; every field required (strict schema), "" or [] when unused."""
    model_config = ConfigDict(extra="forbid")
    name: str
    w0: int
    w1: int
    texts: list[str]
    choice: str
    target: str
    why: str


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(CATALOG.read_text())


def prompt() -> str:
    """The EFFECTS section of the director's instructions, written from the catalog."""
    cat = catalog()
    rows = []
    for name, e in cat["effects"].items():
        f = e["fields"]
        needs = []
        if "texts" in f:
            t = f["texts"]
            needs.append(f"texts: {t['count'][0]}-{t['count'][1]} x up to {t['words']} words ({t['meaning']})")
        if "choice" in f:
            needs.append(f"choice: one of {', '.join(f['choice'])}")
        if "target" in f:
            needs.append(f"target: one of {', '.join(f['target'])}")
        rows.append(f"- {name} ({e['title']}): use when {e['use_when']}. Avoid when {e['avoid_when']}. "
                    f"{'; '.join(needs) or 'no words needed'}.")
    return (f"EFFECTS: signature edits. Use as many as your STYLE allows (its max), favouring its own effects, each "
            f"where it truly fits the words, at least {cat['min_gap']:.0f} s apart, never on the first word; none at all only "
            "when nothing fits. For each: name, w0-w1 (the words it covers), texts/choice/target as listed (\"\" or [] when "
            "not listed), why. Texts are written in the reel's language, short and punchy.\n" + "\n".join(rows))


# ------------------------------------------------------------------ the director's picks -> effect items

def _texts(raw: list[str], spec: dict | None) -> list[str] | None:
    """The texts trimmed to the catalog's limits, or None when there are too few."""
    if not spec:
        return []
    texts = [" ".join(t.split()[:spec["words"]]) for t in raw if t and t.strip()][:spec["count"][1]]
    return texts if len(texts) >= spec["count"][0] else None


def _cut_near(items: list[VideoItem], t: float) -> float | None:
    cuts = [i.out0 for i in items[1:]]
    near = min(cuts, key=lambda c: abs(c - t), default=None)
    return near if near is not None and abs(near - t) <= CUT_SNAP else None


def compile_effects(picks: list[DEffect], words: list[Word], items: list[VideoItem], most: int | None = None) -> list[GraphicItem]:
    """Effect items for the director's picks that pass the catalog: known name, enough words, within limits."""
    from reel_engine.compile import _word_times  # compile imports the director, which imports this module

    cat = catalog()
    total = items[-1].out1 if items else 0.0
    out: list[GraphicItem] = []
    used: dict[str, int] = {}
    last_end = -999.0
    for n, pick in enumerate(sorted(picks, key=lambda p: p.w0)):
        spec = cat["effects"].get(pick.name)
        if not spec or len({g.data["effect"] + str(g.start) for g in out}) >= (most or cat["max_per_reel"]) or used.get(pick.name, 0) >= spec["max"]:
            continue
        span = _word_times(items, words, pick.w0, pick.w1)
        if span is None:
            continue
        start, end = span
        if "cut" in spec["needs"]:
            cut = _cut_near(items, start)
            if cut is None:
                continue
            start, end = cut - ZOOM_HALF, cut + ZOOM_HALF
        else:
            low, high = spec["seconds"]
            end = min(max(end, start + low), start + high, total)
        if start < 0.4 or start - last_end < cat["min_gap"] or end - start < 0.4:
            continue
        fields = spec["fields"]
        texts = _texts(pick.texts, fields.get("texts"))
        if texts is None:
            continue
        out += make_items(f"e{n}", pick.name, start, end, texts, pick.choice, pick.target, pick.why)
        used[pick.name] = used.get(pick.name, 0) + 1
        last_end = end
    if out:
        log.info("Effects: %s", ", ".join(sorted({f"{g.data['effect']}@{g.start:.1f}" for g in out})))
    return out


def make_items(id_: str, name: str, start: float, end: float, texts: list[str], choice: str = "", target: str = "",
               why: str = "") -> list[GraphicItem]:
    """The item(s) for one effect: one, or a back part (under the speaker) and a front part for split effects."""
    spec = catalog()["effects"][name]
    fields = spec["fields"]
    choice = choice if choice in fields.get("choice", []) else (fields.get("choice") or [""])[0]
    target = target if target in fields.get("target", []) else (fields.get("target") or [""])[0]
    data = {"effect": name, "texts": texts, "choice": choice, "target": target, "layer": spec["layer"], "captions": spec["captions"],
            "opaque": bool(spec.get("opaque")), "sound": spec["sound"], "needs": spec["needs"]}
    parts = ["back", "front"] if spec["layer"] == "split" else ["back"] if spec["layer"] == "behind" else ["front"]
    return [GraphicItem(id=f"{id_}{part[0]}", kind="effect", start=round(start, 3), end=round(end, 3), box=[0, 0, W, H],
                        data={**data, "part": part}, place="effect", behind=part == "back", why=why, by="effects") for part in parts]


def clear_under(graphics: list[GraphicItem], effects: list[GraphicItem]) -> list[GraphicItem]:
    """Story graphics give way to an effect on screen at the same time."""
    spans = [(e.start, e.end) for e in effects]
    return [g for g in graphics if g.kind not in YIELDING or not any(a < g.end and g.start < b for a, b in spans)]


# ------------------------------------------------------------------ layout on the speaker

def place_on_faces(plan: EditPlan, picture: Path) -> None:
    """Give effects that need the face its box (output pixels); drop those that need a face and have none."""
    from reel_engine import layout

    keep = []
    seen: dict[tuple[float, float], list[int] | None] = {}
    for g in plan.graphics:
        if g.kind == "effect":
            # Every effect looks for the face: those that need one are dropped without it, text panels just avoid it.
            key = (g.start, g.end)
            if key not in seen:
                faces, _ = layout.look(str(picture), g.start, g.end)
                seen[key] = list(max(faces, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))) if faces else None
            if seen[key] is None and "face" in g.data["needs"]:
                log.info("Effect %s dropped: no face on screen", g.data["effect"])
                continue
            g.data["face"] = seen[key]
            g.data["panel"] = panel_box(seen[key])
        keep.append(g)
    plan.graphics = keep


PANEL_H = 380
SAFE_TOP, SAFE_BOTTOM = 260, 1640


def panel_box(face: list[int] | None) -> list[int]:
    """Where a text panel (glass, paper) goes: clear of the face, in the half of the frame it is not in."""
    if not face:
        return [90, 1180, W - 180, PANEL_H]
    if (face[1] + face[3]) / 2 < H * 0.55:
        top = min(max(face[3] + 40, 1080), SAFE_BOTTOM - PANEL_H)
    else:
        top = max(SAFE_TOP, min(330, face[1] - 40 - PANEL_H))
    return [90, top, W - 180, PANEL_H]


PHONE = (600, 1066)


def phone_screen() -> list[int]:
    w, h = PHONE
    return [(W - w) // 2, (H - h) // 2 + 40, w, h]


# ------------------------------------------------------------------ picture effects

def _ease_out(p: str) -> str:
    return f"(1-pow(1-min(max({p},0),1),3))"


def _zoom_crop(z: str, cx: float, cy: float) -> str:
    """Scale the frame by z(t) about (cx, cy) and crop back to the frame (eval per frame)."""
    return (f"scale=w='2*trunc(iw*({z})/2)':h='2*trunc(ih*({z})/2)':eval=frame,"
            f"crop={W}:{H}:x='min(max({cx}*({z})-{W / 2},0),iw-{W})':y='min(max({cy}*({z})-{H / 2},0),ih-{H})'")


def _centre(g: GraphicItem) -> tuple[float, float]:
    face = g.data.get("face")
    if face and g.data.get("target", "face") != "center":
        return (face[0] + face[2]) / 2, (face[1] + face[3]) / 2
    return W / 2, H / 2


def picture_filter(g: GraphicItem, dur: float, has_matte: bool) -> str | None:
    """The filter graph for one picture effect over its span ([0:v] = the span, [1:v] = the speaker's matte), or None."""
    name = g.data["effect"]
    cx, cy = _centre(g)
    if name == "pullback":
        z = f"1+0.6*(1-{_ease_out(f't/{min(dur, 1.4):.3f}')})"
        return f"[0:v]{_zoom_crop(z, cx, cy)}[out]"
    if name == "zoom_through":
        z = f"1+1.8*pow(max(1-abs(t-{ZOOM_HALF})/{ZOOM_HALF},0),2)"
        return f"[0:v]{_zoom_crop(z, cx, cy)}[out]"
    if name == "vertigo" and has_matte:
        z = f"1+0.45*{_ease_out(f't/{dur:.3f}')}"
        # The zoomed background still holds the speaker, so it is softened into a halo behind the steady cut-out.
        return (f"[0:v]split[a][b];[a]{_zoom_crop(z, cx, cy)},gblur=sigma=14,eq=brightness=-0.08[bg];[1:v]format=gray,scale={W}:{H}[m];"
                f"[b][m]alphamerge[fg];[bg][fg]overlay=0:0[out]")
    if name == "framebreak" and has_matte and g.data.get("face"):
        k = 0.8
        cw, ch = int(W * k) // 2 * 2, int(H * k) // 2 * 2
        ox, oy = (W - cw) // 2, (H - ch) // 2 + 60
        face = g.data["face"]
        cut = int(max(0, (face[1] + (face[3] - face[1]) * 0.45) * k)) // 2 * 2
        return (f"[0:v]split=3[s1][s2][s3];[s1]boxblur=28:4,eq=brightness=-0.14:saturation=0.8[bg];"
                f"[s2]scale={cw}:{ch},crop={cw}:{ch - cut}:0:{cut},drawbox=0:0:iw:ih:white:t=10[card];"
                f"[bg][card]overlay={ox}:{oy + cut}[v1];[1:v]format=gray,scale={cw}:{ch}[m];[s3]scale={cw}:{ch}[fs];"
                f"[fs][m]alphamerge[fg];[v1][fg]overlay={ox}:{oy}[out]")
    if name == "phone_mockup":
        x, y, w, h = phone_screen()
        return (f"[0:v]split[s1][s2];[s1]boxblur=30:4,eq=brightness=-0.2:saturation=0.7[bg];"
                f"[s2]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[scr];[bg][scr]overlay={x}:{y}[out]")
    if name == "glass_type":
        x, y, w, h = g.data["panel"]
        return (f"[0:v]split[s1][s2];[s2]crop={w}:{h}:{x}:{y},gblur=sigma=26,eq=brightness=0.06:saturation=1.1[glass];"
                f"[s1][glass]overlay={x}:{y}[out]")
    return None


async def apply_picture(plan: EditPlan, picture: Path, work: Path) -> Path:
    """The picture with every picture effect rendered into its span (other frames untouched)."""
    fx = sorted((g for g in plan.graphics if g.kind == "effect" and g.data["layer"] == "picture"), key=lambda g: g.start)
    if not fx:
        return picture
    parts, at, n = [], 0.0, 0
    frame = 1 / FPS

    def cut(start: float, end: float, out: Path, graph: str | None = None, matte: Path | None = None) -> None:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(picture)]
        if matte:
            cmd += ["-i", str(matte)]
        cmd += (["-filter_complex", graph, "-map", "[out]"] if graph else []) + [
            "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", str(out)]
        run(cmd)

    for g in fx:
        start, end = round(g.start / frame) * frame, round(g.end / frame) * frame
        if start < at or end <= start:
            continue
        matte = None
        if "matte" in g.data["needs"]:
            matte = work / f"fxmatte_{g.id}.mkv"
            if not await cutout.matte_video(str(picture), start, end, W, H, FPS, str(matte)):
                matte = None
        graph = picture_filter(g, end - start, matte is not None)
        if graph is None:
            log.info("Effect %s skipped: it needs the speaker's matte", g.data["effect"])
            g.data["skipped"] = True
            continue
        if start > at:
            parts.append(work / f"fx_plain{n}.mp4")
            await asyncio.to_thread(cut, at, start, parts[-1])
        parts.append(work / f"fx_{g.id}.mp4")
        try:
            await asyncio.to_thread(cut, start, end, parts[-1], graph, matte)
        except Exception as exc:  # a picture effect that fails leaves the footage as it was
            log.warning("Effect %s failed, footage kept: %s", g.data["effect"], exc)
            g.data["skipped"] = True
            await asyncio.to_thread(cut, start, end, parts[-1])
        at, n = end, n + 1
    if at == 0.0:
        return picture
    parts.append(work / f"fx_plain{n}.mp4")
    await asyncio.to_thread(cut, at, plan.duration, parts[-1])
    listing = work / "fx_parts.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    out = work / "picture_fx.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
    plan.graphics = [g for g in plan.graphics if not g.data.get("skipped")]
    return out


# ------------------------------------------------------------------ what the renderer draws

# Picture effects that also draw something on top (the phone's body, the glass panel's words, a frame label).
DRAWN_PICTURE = {"phone_mockup", "glass_type", "framebreak"}


def drawn(g: GraphicItem) -> bool:
    """Whether the renderer draws a layer for this effect item."""
    if g.data["layer"] != "picture":
        return True
    return g.data["effect"] in DRAWN_PICTURE and (g.data["effect"] != "framebreak" or bool(g.data["texts"]))


def spec_data(g: GraphicItem) -> dict:
    """The effect's fields as the renderer reads them."""
    keys = ("effect", "texts", "choice", "target", "part", "face", "panel", "opaque")
    data = {k: g.data.get(k) for k in keys}
    if g.data["effect"] == "phone_mockup":
        data["screen"] = phone_screen()
    return data
