"""Editing styles (data/styles.json): the house rules a reel is cut by, chosen by the director, held by code.

A style decides which signature effects a reel reaches for and how many it may use, which caption looks it rotates,
which caption styles and music moods fit it, and how often a story graphic appears. Adding a style is an entry in
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
            f"caption styles {', '.join(s['text_styles'])}; moods {', '.join(s['moods'])}; a story graphic every ~{s['graphic_every']} s."
            for name, s in catalog()["styles"].items()]
    return ("STYLE: pick the editing style that fits this creator and this content (style = its name). It is the house "
            "rulebook for the whole reel: reach for its effects (they are what make the style), keep text_style and mood "
            "within its lists, and pace graphics to it.\n" + "\n".join(rows))


def hold(style: dict, text_style: str, mood: str) -> tuple[str, str]:
    """The director's caption style and mood, kept within the style's own (its first choice when they stray)."""
    return (text_style if text_style in style["text_styles"] else style["text_styles"][0],
            mood if mood in style["moods"] else style["moods"][0])
