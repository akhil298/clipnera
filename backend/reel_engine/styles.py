"""Editing styles (data/styles.json): the house rules a reel is cut by, chosen by the director, held by code.

A style decides which signature effects a reel reaches for and how many it may use, which caption looks it rotates,
which music moods fit it, and how often a story graphic appears; the type kits that fit it are listed in the type kit
catalogue (typekits.py). Adding a style is an entry in
the catalog; nothing else changes.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "data" / "styles.json"


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(CATALOG.read_text())


def get(name: str) -> dict:
    cat = catalog()
    return {"name": name, **cat["styles"][name]} if name in cat["styles"] else {"name": cat["default"], **cat["styles"][cat["default"]]}


def names() -> list[str]:
    return list(catalog()["styles"])


def prompt() -> str:
    """The STYLE section of the director's instructions, written from the catalog."""
    rows = [f"- {name} ({s['title']}): for {s['when']}. Favour effects {', '.join(s['effects'])} (up to {s['max_effects']}); "
            f"moods {', '.join(s['moods'])}; a story graphic every ~{s['graphic_every']} s."
            for name, s in catalog()["styles"].items()]
    return ("STYLE: pick the editing style that fits this creator and this content (style = its name). It is the house "
            "rulebook for the whole reel: reach for its effects (they are what make the style), pick a type_kit listed for it, keep "
            "mood within its list, and pace graphics to it.\n" + "\n".join(rows))


def hold(style: dict, mood: str) -> str:
    """The director's music mood, kept within the style's own (its first choice when it strays)."""
    return mood if mood in style["moods"] else style["moods"][0]
