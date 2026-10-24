"""Type kits: the look of a reel's text, picked from a catalogue so reels stop looking alike.

A kit (data/type_kits.json) is a complete type design: the caption font, the big word's font, the title font, their
case and weights, the colours, and how the big word is set off (a block, an outline, a glow, a gradient, a sticker...).
The director picks the kit that fits the content; code holds the pick to the editing style's kits and keeps it from
repeating a kit that a sibling reel (same video) or the creator's recent reels already use. The renderer draws any kit
from its variables (beats/renderer/kits.css), so a new kit is a catalogue entry, not code.
"""

from __future__ import annotations

import colorsys
import json
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np

CATALOG = Path(__file__).resolve().parent / "data" / "type_kits.json"
FALLBACK_ACCENT = "#ffb020"
# How many kits a reel mixes in beside its main one.
MIX_MIN, MIX_MAX = 2, 3


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    return {k["id"]: k for k in json.loads(CATALOG.read_text())["kits"]}


def legible(kit: dict) -> bool:
    """Captions a phone viewer reads at a glance: a lead word of weight 600 or more, or outlined; never thin
    letter-spaced type (a serif-editorial reel's captions read as faint)."""
    treatment = kit.get("lead_treatment")
    return treatment != "spaced" and (kit["lead"]["weight"] >= 600 or treatment in ("stroke", "glow"))


def for_style(style: str) -> list[dict]:
    """The readable kits an editing style may use (every readable kit when the style names none)."""
    kits = [k for k in catalog().values() if style in k["styles"] and legible(k)]
    return kits or [k for k in catalog().values() if legible(k)]


def prompt() -> str:
    """The TYPE KITS section of the director's instructions."""
    rows = [f"- {k['id']} ({', '.join(k['styles'])}): {k['about']}" for k in catalog().values() if legible(k)]
    return ("TYPE KITS (type_kit: the reel's main look, kept for the hook and the payoff line). Pick the kit whose feel fits "
            "this creator, the topic and the footage's colours, from the kits listed for your STYLE; vary it - the same few "
            "kits on every reel is exactly what to avoid.\n"
            f"mix_kits: {MIX_MIN}-{MIX_MAX} more kits that pair with type_kit and contrast with it (another treatment, another "
            "font: a heavy block word beside a clean outline, a sticker beside a soft glow), the way the best human edits mix "
            "several type styles in one reel. Captions take turns through the set a few lines at a time and statements, "
            "labels and titles alternate through it, so pick kits that read as one family of looks.\n" + "\n".join(rows))


def design_prompt() -> str:
    """The TEXT STYLE section: the director designs the reel's type from the fonts and treatments the renderer has."""
    big, lead = treatments()
    return ("TEXT STYLE (text_style): design this reel's own type, the way a top editor styles each client differently - "
            "fitted to the creator, the topic, the footage's colours and the mood. lead = the small words of each caption "
            "line, key = the one big word per line, title = headlines and the call to action. Fonts ONLY from: "
            f"{', '.join(sorted(declared_fonts()))}. Use one or two families (a heavy display face for key/title, a clean "
            "sans for lead); lead weight 600+ (or lead_treatment stroke/glow) so captions read on a phone; key/title "
            f"700-900. treatment (how the big word is set off): one of {', '.join(sorted(big))}; lead_treatment: one of "
            f"{', '.join(sorted(lead - {'spaced'}))}. accent = the big word's colour (strong, readable on the footage), alt = "
            "a second colour, ink = text colour on light cards; all as #rrggbb. type_kit still names the closest catalogue "
            "kit: it is used if your design breaks a rule. why = one line on the design.")


def mix(main: str, picked: list[str], style: str, seed: str = "") -> list[str]:
    """The kits a reel mixes in beside ``main``: the director's picks that exist, read on a phone and differ from the
    main kit, topped up from the style's kits with another treatment and font (stable for a reel via ``seed``)."""
    kits = catalog()
    base = kits.get(main, {})

    def contrasts(k: dict) -> bool:
        return k["id"] != main and legible(k) and (k["treatment"] != base.get("treatment") or k["key"]["font"] != base.get("key", {}).get("font"))

    out = list(dict.fromkeys(p for p in picked if p in kits and contrasts(kits[p])))[:MIX_MAX]
    spare = [k for k in for_style(style) if k["id"] not in out and contrasts(k)]
    while len(out) < MIX_MIN and spare:
        k = spare.pop(zlib.crc32(f"{seed}:{len(out)}".encode()) % len(spare))
        if all(kits[o]["treatment"] != k["treatment"] for o in out):
            out.append(k["id"])
        elif not any(all(kits[o]["treatment"] != s["treatment"] for o in out) for s in spare):
            out.append(k["id"])
    return out


def choose(picked: str, style: str, avoid: set[str] | frozenset[str] = frozenset(), seed: str = "") -> str:
    """The kit for a reel: the director's pick when the style allows it and it is not taken, else another of the
    style's kits sharing its mood (then any free one), chosen by ``seed`` so the choice is stable for a reel."""
    allowed = for_style(style)
    names = [k["id"] for k in allowed]
    if picked in names and picked not in avoid:
        return picked
    free = [k for k in allowed if k["id"] not in avoid] or allowed
    moods = set(catalog().get(picked, {}).get("moods", []))
    near = [k for k in free if moods & set(k["moods"])] or free
    return near[zlib.crc32(seed.encode()) % len(near)]["id"]


def palette_accent(frames: list[np.ndarray]) -> str:
    """A bright accent taken from the footage's own colours: the most common strong hue, pushed vivid; amber when the
    footage has no colour to speak of (grey studio, black and white)."""
    import cv2

    hues = []
    for image in frames:
        hsv = cv2.cvtColor(cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV).reshape(-1, 3)
        strong = hsv[(hsv[:, 1] > 90) & (hsv[:, 2] > 70)]
        hues += strong[:, 0].tolist()
    if len(hues) < 40:
        return FALLBACK_ACCENT
    counts = np.bincount(np.array(hues) // 6, minlength=31)
    hue = (int(np.argmax(counts)) * 6 + 3) / 180
    r, g, b = colorsys.hsv_to_rgb(hue, 0.78, 1.0)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


CLASH_HUE = 0.09      # accents closer than this (share of the colour wheel) to the footage's own colour don't read on it


def _hsv(colour: str) -> tuple[float, float, float]:
    r, g, b = (int(colour[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


def readable(accent: str, alt: str, footage: str) -> str:
    """The accent, unless it is the footage's own colour (peach words on an orange robe): then the kit's second colour
    if that one stands apart, else white."""
    if not footage or footage == FALLBACK_ACCENT:  # no footage colour to clash with
        return accent

    def clash(colour: str) -> bool:
        h1, s1, _ = _hsv(colour)
        h2, _, _ = _hsv(footage)
        return s1 > 0.25 and min(abs(h1 - h2), 1 - abs(h1 - h2)) < CLASH_HUE

    if not clash(accent):
        return accent
    return alt if not clash(alt) and _hsv(alt)[1] > 0.25 else "#ffffff"


@lru_cache(maxsize=1)
def declared_fonts() -> frozenset[str]:
    """Every font family the renderer has a file for (fonts.css, beats.css)."""
    import re

    here = Path(__file__).resolve().parents[1] / "beats" / "renderer"
    css = "".join((here / name).read_text() for name in ("fonts.css", "beats.css"))
    return frozenset(re.findall(r'font-family: "([^"]+)"; (?:font-weight: [^;]+; )?src: url', css))


def treatments() -> tuple[set[str], set[str]]:
    """The big-word and lead-word treatments the renderer draws (kits.css), as the catalogue uses them."""
    kits = catalog().values()
    return {k["treatment"] for k in kits}, {k["lead_treatment"] for k in kits}


def designed(style: dict) -> dict | None:
    """A kit from a type design the director wrote for this reel, or None when it breaks a rule: fonts the renderer
    has, treatments it draws, real colours, legible captions. One renderer draws any kit, so a design is data only."""
    import re

    fonts, (big, lead) = declared_fonts(), treatments()
    colour = re.compile(r"^#[0-9a-fA-F]{6}$")
    parts = {name: {"font": style.get(f"{name}_font", ""), "weight": int(style.get(f"{name}_weight", 700) or 700),
                    "case": style.get(f"{name}_case", "none")} for name in ("lead", "key", "title")}
    if not all(p["font"] in fonts and 400 <= p["weight"] <= 900 and p["case"] in ("none", "uppercase", "lowercase") for p in parts.values()):
        return None
    if style.get("treatment") not in big or style.get("lead_treatment") not in lead:
        return None
    if not all(colour.match(str(style.get(c, ""))) for c in ("accent", "alt", "ink")):
        return None
    kit = {"id": "designed", "about": str(style.get("why", ""))[:200], "styles": [], "moods": [], **parts,
           "treatment": style["treatment"], "lead_treatment": style["lead_treatment"],
           "accent": style["accent"], "alt": style["alt"], "ink": style["ink"]}
    return kit if legible(kit) else None


def spec(kit_id: str, role: str, footage_accent: str = "", kit: dict | None = None) -> dict:
    """What the renderer needs for one graphic: the kit's classes and variables for ``role`` ("text" for captions and
    labels, "title" for titles, chapters and the call to action, which take the kit's title font). ``kit`` is a
    designed kit (see ``designed``), used instead of the catalogue's."""
    kit = kit or catalog().get(kit_id) or next(iter(catalog().values()))
    key = kit["title"] if role == "title" else kit["key"]
    accent = (footage_accent or FALLBACK_ACCENT) if kit["accent"] == "footage" else readable(kit["accent"], kit["alt"], footage_accent)
    return {
        "classes": f"treat-{kit['treatment']} lead-{kit['lead_treatment']}",
        "vars": {
            "--lead-font": f'"{kit["lead"]["font"]}"', "--lead-weight": str(kit["lead"]["weight"]), "--lead-case": kit["lead"]["case"],
            "--key-font": f'"{key["font"]}"', "--key-weight": str(key["weight"]), "--key-case": key["case"],
            "--accent": accent, "--alt": kit["alt"], "--ink": kit["ink"],
        },
    }


def fonts() -> set[str]:
    """Every font family the catalogue uses (the tests check each is declared for the renderer)."""
    return {kit[part]["font"] for kit in catalog().values() for part in ("lead", "key", "title")}
