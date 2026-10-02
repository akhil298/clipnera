"""Short-form formats: AI-detected per video and per clip, each with an edit recipe.

See :mod:`formats.taxonomy` for the formats and their recipes, and
:mod:`formats.visual_probe` for the on-screen evidence they are checked against.
"""

from formats.taxonomy import (
    DEFAULT_FORMAT,
    FORMATS,
    RECIPES,
    Recipe,
    VisualEvidence,
    evidence_from_dict,
    merge_evidence,
    prompt_catalogue,
    recipe_for,
    resolve_format,
    supports,
    visual_format,
)

__all__ = [
    "DEFAULT_FORMAT",
    "FORMATS",
    "RECIPES",
    "Recipe",
    "VisualEvidence",
    "evidence_from_dict",
    "merge_evidence",
    "prompt_catalogue",
    "recipe_for",
    "resolve_format",
    "supports",
    "visual_format",
]
