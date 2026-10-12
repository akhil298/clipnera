"""Keyword search (BM25) over what was said and what each shot shows.

No index to keep: a project's MUDs are small enough to score on every query.
Semantic search (embeddings) can replace this later behind the same tool.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from understanding.mud import MUD

K1 = 1.5
B = 0.75
_TOKEN = re.compile(r"[\w']+")


@dataclass(frozen=True)
class Passage:
    asset_id: str
    kind: Literal["speech", "visual"]
    t0: float
    t1: float
    text: str
    # A shot or utterance id.
    ref: str


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def passages(muds: Mapping[str, MUD], asset_ids: Sequence[str] | None = None) -> list[Passage]:
    wanted = set(asset_ids) if asset_ids else None
    found: list[Passage] = []
    for asset_id in sorted(muds):
        if wanted is not None and asset_id not in wanted:
            continue
        mud = muds[asset_id]
        found += [Passage(asset_id, "speech", u.t0, u.t1, u.text, u.id) for u in mud.utterances]
        found += [Passage(asset_id, "visual", s.t0, s.t1, s.caption, s.id) for s in mud.shots if s.caption]
    return found


def bm25(query: str, docs: Sequence[Passage], top_k: int) -> list[tuple[float, Passage]]:
    terms = tokenize(query)
    if not terms or not docs:
        return []
    bags = [Counter(tokenize(d.text)) for d in docs]
    lengths = [sum(b.values()) for b in bags]
    average = sum(lengths) / len(lengths) or 1.0
    holders = {t: sum(1 for b in bags if t in b) for t in set(terms)}
    scored = []
    for doc, bag, length in zip(docs, bags, lengths):
        score = 0.0
        for term in terms:
            if term not in bag:
                continue
            idf = math.log(1 + (len(docs) - holders[term] + 0.5) / (holders[term] + 0.5))
            freq = bag[term]
            score += idf * freq * (K1 + 1) / (freq + K1 * (1 - B + B * length / average))
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda pair: (-pair[0], pair[1].asset_id, pair[1].t0))
    return scored[:top_k]
