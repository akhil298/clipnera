"""Editorial skills every AI director reads before it plans.

Each skill is a short Markdown file in this folder: rules a good editor follows
(hooks, standalone shorts, titles, motion graphics), written from the research
in ``skills.reference/``. Prompts include them through :func:`skill_block`;
a missing skill is an error, never a silent omission, so no director plans
without the rules it is meant to follow.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
HOOKS = "hooks"
STANDALONE_SHORTS = "standalone_shorts"
TITLES = "titles"
MOTION_GRAPHICS = "motion_graphics"


@lru_cache(maxsize=None)
def skill(name: str) -> str:
    """The body of one skill, its front matter removed. Raises when the skill file is missing."""
    path = SKILLS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Director skill '{name}' is missing at {path}")
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("---"):
        text = text.split("---", 2)[2].strip()
    return text


def skill_block(*names: str) -> str:
    """The named skills as one prompt section, in the order given."""
    return "Read these editing skills first and follow them in every decision.\n\n" + "\n\n".join(
        skill(name) for name in names
    )
