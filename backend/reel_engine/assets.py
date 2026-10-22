"""The asset loop: search every scope, make what is missing, check it, store it so the next reel finds it.

Agents ask for what they need ("fried egg" icon, "sizzle" sound, an "upbeat" bed, a score for these cuts);
the Scout searches in order - the user's own assets, the global kit, everything made before, the built-in
libraries - and hands misses to the Generator. The Librarian checks every made asset, records its licence
and how it was made, sets its scope (global for generic assets, private for anything from the user's
footage), and stores it in the registry with search words, so the library grows with every reel.

Two registry backends share one interface: ``LocalAssetStore`` (a folder and an index, for the CLI and
tests) and ``DbAssetStore`` in ``reel_engine.store`` (the ``reel_assets`` table and S3, for the product).
"""

from __future__ import annotations

import json
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from beats import kit
from core.logging_config import get_logger
from reel_engine.plan import AssetRef

log = get_logger(__name__)

STATIC = Path(__file__).resolve().parents[1] / "static" / "motion"
LICENCE_MADE = "Clipnera original, made in code"
Scope = Literal["global", "user"]


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str
    scope: Scope = "global"
    owner: str = ""
    path: str = ""
    words: list[str] = Field(default_factory=list)
    description: str = ""
    licence: str = LICENCE_MADE
    source: str = ""
    made_by: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)
    uses: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def ref(self, made: bool = False) -> AssetRef:
        return AssetRef(id=self.id, kind=self.kind, path=self.path, licence=self.licence, source=self.source, made=made)


class AssetStore(ABC):
    @abstractmethod
    async def search(self, kind: str, words: set[str], owner: str) -> list[AssetRecord]:
        """Records of ``kind`` visible to ``owner`` (theirs and global), best word match first."""

    @abstractmethod
    async def add(self, record: AssetRecord, file: Path) -> AssetRecord:
        """Store ``file`` and its record; returns the record with its stored path."""

    @abstractmethod
    async def local(self, record: AssetRecord, work: Path) -> Path:
        """A local copy of the asset's file, for rendering."""

    async def used(self, ids: list[str]) -> None:
        return None


def match(records: list[AssetRecord], words: set[str]) -> list[AssetRecord]:
    scored = [(len(words & set(r.words)), r.uses, r) for r in records]
    return [r for score, _, r in sorted(scored, key=lambda x: (-x[0], -x[1])) if score > 0]


class LocalAssetStore(AssetStore):
    """A folder with an ``index.json``: the registry for command-line runs and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = root / "index.json"

    def _load(self) -> list[AssetRecord]:
        if not self.index.exists():
            return []
        return [AssetRecord(**r) for r in json.loads(self.index.read_text())]

    def _save(self, records: list[AssetRecord]) -> None:
        self.index.write_text(json.dumps([r.model_dump() for r in records], indent=1))

    async def search(self, kind: str, words: set[str], owner: str) -> list[AssetRecord]:
        return match([r for r in self._load() if r.kind == kind and (r.scope == "global" or r.owner == owner)], words)

    async def add(self, record: AssetRecord, file: Path) -> AssetRecord:
        target = self.root / record.kind / f"{record.id}{file.suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
        record.path = str(target)
        self._save([*self._load(), record])
        return record

    async def local(self, record: AssetRecord, work: Path) -> Path:
        return Path(record.path)

    async def used(self, ids: list[str]) -> None:
        records = self._load()
        for r in records:
            if r.id in ids:
                r.uses += 1
        self._save(records)


class Scout:
    """Finds or makes every asset a plan asks for, and keeps a list of what it made."""

    def __init__(self, store: AssetStore, owner: str, work: Path) -> None:
        self.store, self.owner, self.work = store, owner, work
        self.made: list[AssetRecord] = []
        self.used: list[str] = []
        self.misses: list[str] = []
        self._score: AssetRef | None = None

    # ---- icons and logos: the user's own, then the kit, then what was made before
    async def icon(self, query: str) -> AssetRef | None:
        words = kit.words_of(query)
        if not words:
            return None
        found = await self.store.search("icon", words, self.owner)
        if found:
            return await self._reuse(found[0])
        entry = kit.find(("object3d",), query, query) or kit.find(("icon_line",), query, query) or kit.logo(query)
        if entry and kit.path_of(entry):
            return AssetRef(id=entry["id"], kind="icon", path=str(kit.path_of(entry)), licence=entry.get("licence", ""),
                            source=entry.get("source", "kit"))
        self.misses.append(f"icon: {query}")
        return None

    # ---- sounds: the curated pack and the synth pack, then made sounds, then made on demand
    async def sound(self, name: str) -> AssetRef | None:
        from motion.sound import manifest

        if name in manifest():
            return AssetRef(id=f"sfx.{name}", kind="sfx", path=str(STATIC / "sfx" / manifest()[name]["file"]),
                            licence=manifest()[name].get("licence", ""), source="sfx pack")
        synth = _synth_manifest()
        tagged = next((key for key, entry in synth.items() if name in entry.get("tags", []) or key.startswith(name)), None)
        if tagged:
            entry = synth[tagged]
            return AssetRef(id=f"sfx.synth.{tagged}", kind="sfx", path=str(STATIC / "sfx" / "synth" / entry["file"]),
                            licence=entry.get("licence", ""), source="synth pack")
        found = await self.store.search("sfx", {name}, self.owner)
        if found:
            return await self._reuse(found[0])
        return await self._make_sound(name)

    async def _make_sound(self, name: str) -> AssetRef | None:
        from reel_engine import music

        if name not in music.FOLEY:
            self.misses.append(f"sound: {name}")
            return None
        path = music.write_foley(name, self.work / f"made_{name}.wav")
        record = AssetRecord(kind="sfx", scope="global", words=[name], description=f"{name} sound, synthesised",
                             source="reel_engine.music.foley", made_by={"recipe": name})
        return await self._keep(record, path)

    # ---- music: a bed from the library by mood, or a score made for this edit
    def bed(self, mood: str) -> AssetRef | None:
        beds = json.loads((STATIC / "music" / "manifest.json").read_text())
        pick = next((k for k, v in beds.items() if v.get("mood") == mood), None) or \
            next((k for k, v in beds.items() if mood in v.get("tags", [])), None) or next(iter(beds), None)
        if not pick:
            return None
        return AssetRef(id=f"music.{pick}", kind="music", path=str(STATIC / "music" / beds[pick]["file"]),
                        licence=beds[pick].get("licence", ""), source="music beds")

    async def score(self, structure, reel: str) -> AssetRef:
        """The score for this edit, composed once; revision passes reuse it."""
        from reel_engine import music

        if self._score:
            return self._score
        path = music.compose(structure, self.work / "score.wav")
        record = AssetRecord(kind="score", scope="user", owner=self.owner, words=["score", structure.mood],
                             description=f"score composed for reel {reel}", source="reel_engine.music.compose",
                             made_by={"bpm": music.BPM, "mood": structure.mood, "sections": len(structure.sections)},
                             meta={"seconds": round(structure.duration, 2)})
        self._score = await self._keep(record, path)
        return self._score

    async def _reuse(self, record: AssetRecord) -> AssetRef:
        self.used.append(record.id)
        local = await self.store.local(record, self.work)
        return record.ref().model_copy(update={"path": str(local)})

    # ---- the Librarian: check, record, store
    async def _keep(self, record: AssetRecord, file: Path) -> AssetRef:
        if not file.exists() or file.stat().st_size < 64:
            raise RuntimeError(f"made asset {record.kind} is empty")
        stored = await self.store.add(record, file)
        self.made.append(stored)
        log.info("Librarian stored %s %s (%s)", stored.kind, stored.id, stored.scope)
        return stored.ref(made=True).model_copy(update={"path": str(file)})

    async def finish(self) -> None:
        if self.used:
            await self.store.used(self.used)


def _synth_manifest() -> dict:
    path = STATIC / "sfx" / "synth" / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else {}
