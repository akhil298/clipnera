"""Explainer scenes: what the speaker explains, shown as a small 3D world the reel cuts to while the voice carries on.

The director picks a shot from the catalog (data/scenes.json: reveal, inside, compare, many, force, transform, flow,
cycle, scale, wrong, location), a world (sky, space, macro, body, ocean, room, studio, city) and the actors by name.
Each actor is a built 3D form when one fits (cloud, raindrop, coin, atom...) or else the kit's 3D object that
literally shows it, chosen by one text call; a scene whose actors cannot be shown is dropped, or, when switched on,
made with Veo instead. Labels are the director's, held to what is said: a figure on a label must be the figure
spoken. The scenes are drawn by the beats renderer (beats/renderer/scene.js) and laid over the picture as cutaways.
"""

from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.config import get_settings
from core.logging_config import get_logger
from reel_engine.plan import AssetRef, EditPlan, InsertItem, VideoItem, Word

log = get_logger(__name__)

CATALOG = Path(__file__).parent / "data" / "scenes.json"
Shot = Literal["reveal", "inside", "compare", "many", "force", "transform", "flow", "cycle", "scale", "wrong", "location"]
World = Literal["sky", "space", "macro", "body", "ocean", "room", "studio", "city"]
# Story graphics that would sit on a 3D scene give way to it; the captions and the progress bar carry on.
KEEP_OVER = {"progress", "hook", "accent"}
# The speaker's face opens the reel this long before a scene may cut in.
HOOK_FACE = 0.6
# A scene frame drawn without a GPU (the worker's software WebGL) takes far longer than a 2D graphic's.
SCENE_FRAME_SECONDS = 2.5
VEO_PROMPT = ("Vertical 9:16 stylised 3D animated explainer shot, soft clay-like materials, bright clean lighting, slow smooth "
              "camera move, like a premium science channel: {what}. No text, no letters, no logos, no people's faces.")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DActor(_M):
    show: str
    label: str


class DScene(_M):
    shot: Shot
    world: World
    w0: int
    w1: int
    actors: list[DActor]
    number: str
    ratio: float
    direction: Literal["up", "down", "left", "right", "none"]
    place: str
    lat: float
    lon: float
    why: str


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(CATALOG.read_text())


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    return {alias: form for form, names in catalog()["forms"].items() for alias in [form, *names]}


def form_of(show: str) -> str | None:
    """The built 3D form that shows ``show``, or None (the kit is asked instead)."""
    key = re.sub(r"\s+", " ", show.lower().strip())
    return _aliases().get(key) or _aliases().get(key.removesuffix("s"))


def prompt() -> str:
    """The SCENES section of the director's instructions, written from the catalog."""
    cat = catalog()
    shots = "\n".join(f"- {name} ({s['actors'][0]}-{s['actors'][1]} actors): {s['use_when']}" for name, s in cat["shots"].items())
    worlds = "\n".join(f"- {name}: {about}" for name, about in cat["worlds"].items())
    return (f"SCENES (explainer scenes, about one every 6-10 s while a speaker EXPLAINS how or why something works - science, "
            f"health, money, how-things-work; at most {get_settings().REEL_MAX_SCENES}; none for chat, stories, reactions or "
            "advice with nothing to show): a 3D animated scene the reel cuts to while the voice carries on, like a premium "
            "explainer channel. It beats a photo whenever the words describe a mechanism, a process, a comparison, an amount "
            "or something invisible. w0..w1 = the words it covers (2-4.5 s). When the hook names the surprising thing (\"a "
            "cloud weighs 5 lakh kg\"), open on its scene: the headline stays over it. Pick a shot and a world:\n"
            f"SHOTS:\n{shots}\nWORLDS:\n{worlds}\n"
            "actors: show = 1-3 plain English words naming ONE concrete thing (\"raindrop\", \"heat\", \"lungs\", \"bank\", "
            "\"money\", \"phone battery\"); label = 1-3 words printed on a pinned label, in the reel's language as spoken, "
            "or \"\" (labels name what is shown or the figure said: \"5 LAKH KG\", \"HEAT\", \"Water droplets\"; never a sentence). "
            "number = the count or amount said (many, scale) else \"\"; ratio = compare sizes else 0; direction for force "
            "else \"none\"; place/lat/lon for location else \"\" and 0. why = the line it shows. Scenes and inserts never "
            "overlap: an explainer reel uses scenes where it explains and photos where it names real things.")


def _digits(text: str) -> str:
    return "".join(ch for ch in text.translate(str.maketrans("०१२३४५६७८९", "0123456789")) if ch.isdigit())


def proven(label: str, said: str) -> str:
    """``label``, unless it carries a figure the speaker did not say (a figure spoken as digits must match digit for
    digit; one spoken in words cannot be checked and stands)."""
    shown, spoken = _digits(label), _digits(said)
    return "" if shown and spoken and shown not in spoken else label


def placed(scenes: list[DScene], items: list[VideoItem], words: list[Word]) -> list[tuple[float, float, DScene]]:
    """Scenes on the cut: (start, end, scene), apart, each its catalog length; at most REEL_MAX_SCENES. A scene may
    open on the hook's line (the hook headline stays over it), just not in its first moment, so the face is seen."""
    from reel_engine.compile import to_output  # compile imports the director, which imports this module

    lo, hi = catalog()["seconds"]
    out: list[tuple[float, float, DScene]] = []
    for scene in scenes:
        if not (0 <= scene.w0 < len(words)) or scene.shot not in catalog()["shots"]:
            continue
        first, last = words[scene.w0], words[min(max(scene.w1, scene.w0), len(words) - 1)]
        start, end = to_output(items, first.src, first.t0), to_output(items, last.src, last.t1)
        if start is None or start < HOOK_FACE:
            continue
        end = min(max(end or start + lo, start + lo), start + hi, items[-1].out1 - 0.2)
        if end - start < lo * 0.8 or any(a < end and start < b for a, b, _ in out):
            continue
        out.append((round(start, 3), round(end, 3), scene))
        if len(out) >= get_settings().REEL_MAX_SCENES:
            break
    return out


async def resolve(scenes: list[DScene], items: list[VideoItem], words: list[Word]) -> list[tuple[float, float, DScene, list[dict] | None]]:
    """Each placed scene with its actors as renderer specs, or None when they cannot be shown."""
    from reel_engine import icons

    spots = placed(scenes, items, words)
    asks: list[tuple[int, int, str, str]] = []
    for n, (_, _, scene) in enumerate(spots):
        for k, actor in enumerate(scene.actors[:4]):
            if not form_of(actor.show):
                asks.append((n, k, actor.show, f"{actor.label}; {scene.why}"))
    # Many kit icons share a word (a dozen hearts): a scene's subject is chosen from a wider pool than a caption's icon.
    found = await icons.choose([(show, ctx) for _, _, show, ctx in asks], kinds=("object3d",), n=16) if asks else []
    pictures = {(n, k): asset.path for (n, k, _, _), asset in zip(asks, found) if asset}
    out = []
    for n, (start, end, scene) in enumerate(spots):
        said = " ".join(w.text for w in words[scene.w0:scene.w1 + 1])
        actors, subject = [], False
        for k, actor in enumerate(scene.actors[:4]):
            form, picture = form_of(actor.show), pictures.get((n, k))
            if form or picture:
                spec = {"form": form} if form else {"img": Path(picture).resolve().as_uri()}
                actors.append({**spec, "label": proven(actor.label.strip(), said)[:24]})
                subject = subject or k == 0
        # The first actor is what the scene is about: arrows lifting nothing (its price tag not in the kit) say nothing.
        least, _ = catalog()["shots"][scene.shot]["actors"]
        shows = scene.shot == "location" or (subject and len(actors) >= least)
        out.append((start, end, scene, actors if shows else None))
    return out


def vivid(accent: str, fallback: str = "#ffb020") -> str:
    """``accent`` when it is a strong colour, else ``fallback``: a reel's accent taken from pale footage came out white,
    and white arrows vanished on the studio's pale set."""
    try:
        r, g, b = (int(accent.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return fallback
    hi, lo = max(r, g, b), min(r, g, b)
    return accent if hi - lo >= 0.35 and 0.25 <= (hi + lo) / 2 <= 0.75 else fallback


def spec(item_id: str, length: float, scene: DScene, actors: list[dict], accent: str) -> dict:
    """The renderer's spec for one scene (beats/renderer/scene.js)."""
    world = "space" if scene.shot == "location" else scene.world
    return {"id": item_id, "kind": "scene", "dur": round(length, 3), "world": world, "shot": scene.shot, "actors": actors,
            "number": scene.number.strip()[:24], "ratio": scene.ratio, "direction": scene.direction if scene.direction != "none" else "up",
            "place": {"name": scene.place[:24], "lat": scene.lat, "lon": scene.lon} if scene.shot == "location" else None,
            "accent": vivid(accent), "seed": item_id}


async def _veo(scene: DScene, out: Path) -> Path | None:
    from broll.generation import VeoClient
    from usage.recorder import record_llm_call

    settings = get_settings()
    what = "; ".join(a.show for a in scene.actors) + f" - showing: {scene.why[:160]}"
    started = time.monotonic()
    try:
        await VeoClient(settings.GEMINI_API_KEY, settings.VEO_MODEL).generate(VEO_PROMPT.format(what=what), 4, settings.VEO_RESOLUTION, out)
    except Exception as exc:  # a scene Veo cannot make is left out; the speaker stays on screen
        log.warning("Veo scene failed for %r: %s", what[:80], str(exc)[:200])
        return None
    await record_llm_call("gemini", settings.VEO_MODEL, video_seconds=4.0, resolution=settings.VEO_RESOLUTION,
                          latency_ms=int((time.monotonic() - started) * 1000))
    return out


async def build(scenes: list[DScene], plan: EditPlan, words: list[Word], work: Path) -> list[InsertItem]:
    """The reel's explainer scenes, drawn, as full-frame inserts."""
    from reel_engine.render import _draw

    settings = get_settings()
    if not (settings.REEL_SCENES and scenes):
        return []
    work = work / "scenes"
    work.mkdir(parents=True, exist_ok=True)
    resolved = await resolve(scenes, plan.video, words)
    accent = plan.brief.accent if plan.brief else "#ffb020"
    specs, made, veo_left = [], {}, settings.REEL_SCENE_VEO_MAX if settings.REEL_SCENE_VEO and settings.GEMINI_API_KEY else 0
    for n, (start, end, scene, actors) in enumerate(resolved):
        if actors is not None:
            specs.append(spec(f"x{n}", end - start, scene, actors, accent))
        elif veo_left > 0:
            veo_left -= 1
            made[f"x{n}"] = await _veo(scene, work / f"veo_x{n}.mp4")
    try:
        drawn = await _draw(specs, work, SCENE_FRAME_SECONDS) if specs else {}
    except Exception as exc:  # scenes that cannot be drawn are left out; the reel goes on with photos and graphics
        log.warning("Scenes not drawn: %s", exc)
        drawn = {}
    out = []
    for n, (start, end, scene, _) in enumerate(resolved):
        file = (drawn.get(f"x{n}") or {}).get("file") or made.get(f"x{n}")
        if not file:
            continue
        label = next((a.label for a in scene.actors if a.label), "")
        out.append(InsertItem(id=f"x{n}", kind="scene", start=start, end=end, label=label[:28], query=scene.why[:200],
                              asset=AssetRef(id=f"scene_x{n}", kind="scene", path=str(file), licence="made by Clipnera",
                                             source="veo" if f"x{n}" in made else "scene", made=True)))
    log.info("Scenes: %d drawn of %d asked (%d with Veo)", len(out), len(scenes), sum(1 for f in made.values() if f))
    return out


def make_room(plan: EditPlan, scenes: list[InsertItem]) -> None:
    """Scenes take their stretch: other inserts and story graphics under one give way (captions carry on)."""
    def under(a, b) -> bool:
        return any(s.start < b and a < s.end for s in scenes)

    plan.inserts = sorted(scenes + [i for i in plan.inserts if not under(i.start, i.end)], key=lambda i: i.start)
    plan.graphics = [g for g in plan.graphics if g.kind in KEEP_OVER or not under(g.start, g.end)]


def clear_requests(requests: list, scenes: list[InsertItem], items: list[VideoItem], words: list[Word]) -> list:
    """The director's photo and B-roll requests that do not fall under a scene (nothing is fetched for those)."""
    from reel_engine.compile import to_output

    def at(w: int) -> float | None:
        return to_output(items, words[w].src, words[w].t0) if 0 <= w < len(words) else None

    keep = []
    for r in requests:
        t = at(r.w0)
        if t is None or not any(s.start - 0.5 <= t < s.end for s in scenes):
            keep.append(r)
    return keep
