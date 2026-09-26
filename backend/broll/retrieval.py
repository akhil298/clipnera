"""Find the best library shot for each scene of a reel.

One pass per reel: every scene's candidates come from Postgres full-text search
(any of the scene's words), then are scored on how much of the scene they cover,
text rank, quality, meaning (when embeddings are on) and how rarely users swap
them out. Scenes are filled in order and a shot, or another shot of the same
source clip, is never used twice in one reel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from broll.embeddings import Embedder, cosine
from broll.model import BrollAsset
from broll.repository import BrollRepository, Candidate

CANDIDATES_PER_SCENE = 60
ALTERNATES = 3
_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have in into is it its of on or that the this to was were with "
    "very really just about over under up down out".split()
)
_WORD = re.compile(r"[a-z0-9]+")


@dataclass
class SceneQuery:
    text: str
    min_duration: float = 0.0


@dataclass
class Scored:
    asset: BrollAsset
    score: float
    coverage: float


@dataclass
class ScenePicks:
    query: SceneQuery
    ranked: list[Scored] = field(default_factory=list)

    @property
    def best(self) -> Scored | None:
        return self.ranked[0] if self.ranked else None


def terms(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for word in _WORD.findall(text.lower()):
        if word not in _STOPWORDS and len(word) > 1:
            seen.setdefault(word, None)
    return list(seen)


def stem(word: str) -> str:
    """Just enough English stemming to match plurals and verb forms ("cities"/"city", "running"/"run")."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix) and not word.endswith("ss"):
            root = word[: -len(suffix)]
            # "running" -> "runn" -> "run", "stopped" -> "stop"
            if suffix != "s" and len(root) > 2 and root[-1] == root[-2] and root[-1] not in "aeiouls":
                root = root[:-1]
            return root
    return word


def _same_word(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def coverage(query_terms: list[str], asset_text: str) -> float:
    """Share of the scene's words the shot's description contains, allowing for word forms."""
    if not query_terms:
        return 0.0
    words = {stem(w) for w in _WORD.findall(asset_text.lower()) if len(w) > 2}
    hits = sum(1 for term in query_terms if any(_same_word(stem(term), w) for w in words))
    return hits / len(query_terms)


def score(candidate: Candidate, cover: float, top_rank: float, similarity: float | None, swap_rate: float) -> float:
    rank = candidate.text_rank / top_rank if top_rank > 0 else 0.0
    if similarity is None:
        return 0.55 * cover + 0.15 * rank + 0.15 * candidate.asset.quality_score + 0.15 * (1 - swap_rate)
    return 0.40 * cover + 0.10 * rank + 0.15 * candidate.asset.quality_score + 0.25 * similarity + 0.10 * (1 - swap_rate)


class BrollRetriever:
    def __init__(self, repo: BrollRepository, embedder: Embedder | None = None) -> None:
        self._repo = repo
        self._embedder = embedder

    async def find(
        self, scenes: list[SceneQuery], *, user_id: str | None = None, commercial: bool = False,
    ) -> list[ScenePicks]:
        recent = await self._repo.recently_used(user_id) if user_id else set()
        vectors = await self._embedder.embed([s.text for s in scenes]) if self._embedder and scenes else [None] * len(scenes)
        used_sources: set[tuple[str, str]] = set()
        results: list[ScenePicks] = []
        for scene, vector in zip(scenes, vectors):
            query_terms = terms(scene.text)
            picks = ScenePicks(scene)
            results.append(picks)
            if not query_terms:
                continue
            candidates = await self._repo.search(
                " or ".join(query_terms), min_duration=scene.min_duration, user_id=user_id,
                commercial=commercial, exclude_ids=list(recent), limit=CANDIDATES_PER_SCENE,
            )
            candidates = [c for c in candidates if (c.asset.source, c.asset.source_id) not in used_sources]
            if not candidates:
                continue
            swaps = await self._repo.swap_rates([c.asset.id for c in candidates])
            top_rank = max(c.text_rank for c in candidates)
            scored = []
            for candidate in candidates:
                cover = coverage(query_terms, candidate.asset.search_text)
                similarity = cosine(vector, candidate.asset.embedding) if vector and candidate.asset.embedding else None
                scored.append(Scored(candidate.asset, round(score(candidate, cover, top_rank, similarity, swaps.get(candidate.asset.id, 0.0)), 4), cover))
            scored.sort(key=lambda s: s.score, reverse=True)
            picks.ranked = scored[: 1 + ALTERNATES]
            used_sources.add((scored[0].asset.source, scored[0].asset.source_id))
        return results
