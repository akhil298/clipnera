"""The free-licence music library: which licences we accept and how a track is picked.

We buy no music. A track is added only with a complete licence record (see
``edit_engine.model.MusicTrack``) under a licence that allows commercial use
and editing. NC (non-commercial) and ND (no derivatives) licences are refused
outright, and SA (share-alike) too, since it could put the creator's whole
reel under the same licence.
"""

from __future__ import annotations

import hashlib
from typing import Any

from core.exceptions import CustomException

# licence code -> (deed URL, credit needed)
ALLOWED_LICENCES: dict[str, tuple[str, bool]] = {
    "CC0": ("https://creativecommons.org/publicdomain/zero/1.0/", False),
    "CC-BY-3.0": ("https://creativecommons.org/licenses/by/3.0/", True),
    "CC-BY-4.0": ("https://creativecommons.org/licenses/by/4.0/", True),
    "PIXABAY": ("https://pixabay.com/service/license-summary/", False),
}
SOURCES = ("openverse", "fma", "ccmixter", "incompetech", "pixabay", "freesound", "other")
MOODS = ("upbeat", "chill", "lofi", "inspiring", "cinematic", "dramatic", "emotional", "funny", "energetic", "corporate")
ENERGY_LEVELS = {"low": 0.25, "medium": 0.5, "high": 0.8}


def credit_line(title: str, artist: str, licence: str, source_url: str) -> str:
    """The attribution a CC BY licence asks for: title, author, licence and source."""
    return f"Music: “{title}” by {artist}, {licence.replace('-', ' ')} ({source_url})"


def validate_licence(licence: str, commercial_ok: bool, edit_ok: bool, credit_text: str) -> str:
    """The licence deed URL, or a 400 explaining why the track cannot be added."""
    if licence not in ALLOWED_LICENCES:
        raise CustomException(
            message=f"{licence} is not an accepted licence. Use one of: {', '.join(ALLOWED_LICENCES)}.",
            code="LICENCE_NOT_ALLOWED", status_code=400,
        )
    if not (commercial_ok and edit_ok):
        raise CustomException(
            message="Only tracks whose licence allows commercial use and editing can be added.",
            code="LICENCE_NOT_ALLOWED", status_code=400,
        )
    deed, needs_credit = ALLOWED_LICENCES[licence]
    if needs_credit and not credit_text.strip():
        raise CustomException(message=f"{licence} needs a credit line.", code="CREDIT_REQUIRED", status_code=400)
    return deed


def pick_track(tracks: list[Any], mood: str, energy: str, seed: str) -> Any | None:
    """A live track in the mood (else any), closest in energy; ``seed`` spreads picks across equals."""
    if not tracks:
        return None
    in_mood = [t for t in tracks if t.mood == mood] or tracks
    target = ENERGY_LEVELS.get(energy, 0.5)
    best = min(abs(t.energy - target) for t in in_mood)
    closest = sorted((t for t in in_mood if abs(t.energy - target) <= best + 0.15), key=lambda t: t.id)
    return closest[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(closest)]
