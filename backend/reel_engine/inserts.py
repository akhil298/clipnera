"""Inserts: the related pictures a premium edit cuts to while someone talks - B-roll, photos, the user's other shots.

The director asks for an insert on the words that name something ("the space station", "fresh croissants")
with search words. The Scout looks in order: the registry (anything found before), public-domain and CC0
photos (Openverse, NASA) and video (NASA, Wikimedia Commons), or the user's own unused footage. One vision
call sees the candidates of every request and picks the one that shows the thing, or none; picks are stored
in the registry for the next reel. Video and photo inserts are full-frame cutaways (the voice carries on);
some photos become framed photo cards beside the speaker instead.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from beats import kit
from broll.sources.base import USER_AGENT
from core.config import get_settings
from core.logging_config import get_logger
from reel_engine import imagery
from reel_engine.ai import vision_json
from reel_engine.assets import AssetRecord, Scout
from reel_engine.compile import to_output
from reel_engine.media import INTERMEDIATE_PRESET, frame, jpeg
from reel_engine.plan import AssetRef, InsertItem, VideoItem, Word

log = get_logger(__name__)

MAX_INSERTS = 16
CANDIDATES = 3
MIN_SECONDS, MAX_SECONDS = 1.2, 3.2
MAX_VIDEO_BYTES = 80 * 1024 * 1024
FREE_LICENCES = {"public_domain", "pd_us_gov", "cc0"}
CHOOSER = """You pick the pictures a premium editor cuts to while someone talks. For each request you get what is
being said and 1-3 candidate images (photos, or a frame of a video clip). Pick the candidate that clearly shows the
requested thing in a way that looks good full screen in a vertical reel; pick -1 when none does (wrong subject,
text-heavy, a logo or diagram when a photo was wanted, ugly or tiny). JSON only."""


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pick(_M):
    request: int
    candidate: int
    why: str


class Picks(_M):
    picks: list[Pick]


async def _download(url: str, target: Path, limit: int) -> Path | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=True,
                                     headers={"User-Agent": USER_AGENT}) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200 or int(response.headers.get("content-length") or 0) > limit:
                    return None
                size = 0
                with target.open("wb") as f:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > limit:
                            return None
                        f.write(chunk)
        return target if target.stat().st_size > 1024 else None
    except (httpx.HTTPError, OSError) as exc:
        log.info("Insert download failed %s: %s", url[:80], exc)
        return None


async def _candidates(kind: str, query: str, work: Path, n: int) -> list[tuple[Path, dict]]:
    """Downloaded candidates (file, licence record) for a photo or B-roll request."""
    from broll.sources.nasa import NasaSource
    from broll.sources.photos import NasaPhotos, OpenversePhotos, WikimediaPhotos
    from broll.sources.wikimedia import WikimediaSource

    sources = [WikimediaPhotos(), OpenversePhotos(), NasaPhotos()] if kind == "photo" else [NasaSource(), WikimediaSource()]
    found = []
    for result in await asyncio.gather(*(s.search(query, CANDIDATES) for s in sources), return_exceptions=True):
        if isinstance(result, Exception):
            log.info("Insert search failed for %r: %s", query, result)
            continue
        found += [c for c in result if c.license_code in FREE_LICENCES]
    async def fetch(c) -> tuple[Path, dict] | None:
        suffix = Path(c.download_url.split("?")[0]).suffix.lower() or (".jpg" if kind == "photo" else ".mp4")
        target = work / f"cand_{abs(hash(c.download_url)) % 10**9}{suffix}"
        got = await _download(c.download_url, target, 15 * 1024 * 1024 if kind == "photo" else MAX_VIDEO_BYTES)
        return (got, {"source": c.source, "source_url": c.source_url, "licence": c.license_code, "title": c.title,
                      "author": c.author or "", "license_url": c.license_url or ""}) if got else None

    fetched = await asyncio.gather(*(fetch(c) for c in found[: n + 1]))
    return [f for f in fetched if f][:n]


def _preview(path: Path, kind: str) -> bytes:
    image = frame(path, 1.0 if kind == "broll" else 0.0, 360)
    return jpeg(image) if image is not None else b""


async def resolve(requests: list, items: list[VideoItem], words: list[Word], scout: Scout, work: Path,
                  sources: dict[int, str], shots_per_source: dict[int, int] | None = None) -> tuple[list[InsertItem], int]:
    """Inserts placed on the cut, with their assets; and how many vision calls it took."""
    # The user's own footage only helps when it holds other shots; a single take would cut to the same picture.
    requests = [r for r in requests if r.kind != "footage" or (shots_per_source or {}).get(r.src, 0) >= 3]
    work = work / "inserts"
    work.mkdir(exist_ok=True)
    placed: list[tuple[float, float, object]] = []
    for request in requests[:MAX_INSERTS]:
        if 0 <= request.w0 < len(words):
            w = words[request.w0]
            start = to_output(items, w.src, w.t0)
            last = words[min(max(request.w1, request.w0), len(words) - 1)]
            end = to_output(items, last.src, last.t1)
        else:
            start = to_output(items, request.src, request.at) if request.src in sources else None
            end = None
        if start is None:
            continue
        end = min(max(end or start + 2.0, start + MIN_SECONDS), start + MAX_SECONDS, items[-1].out1 - 0.2)
        if end - start < MIN_SECONDS * 0.8 or any(a < end and start < b for a, b, _ in placed):
            continue
        placed.append((start, end, request))

    # Look up every request: the registry first, else download candidates.
    found: dict[int, AssetRef] = {}
    pending: list[tuple[int, list[tuple[Path, dict]]]] = []
    async def look(n: int, request) -> None:
        reuse = await scout.store.search(request.kind, kit.words_of(request.query), scout.owner)
        if reuse:
            found[n] = await scout._reuse(reuse[0])
            return
        cands = await _candidates(request.kind, request.query, work, CANDIDATES)
        if not cands and request.kind == "broll":
            # Public-domain video covers space, science, nature and history; everyday things fall back to a photo.
            cands = await _candidates("photo", request.query, work, CANDIDATES)
            if cands:
                placed[n] = (placed[n][0], placed[n][1], request.model_copy(update={"kind": "photo"}))
        if cands:
            pending.append((n, cands))
        else:
            scout.misses.append(f"{request.kind}: {request.query}")

    await asyncio.gather(*(look(n, request) for n, (_, _, request) in enumerate(placed) if request.kind != "footage"))
    pending.sort(key=lambda p: p[0])
    calls = 0
    if pending:
        jpegs, lines = [], []
        for n, cands in pending:
            _, _, request = placed[n]
            lines.append(f"request {n}: {request.kind} of '{request.query}' while saying: {request.why[:80]}; "
                         f"candidates {len(cands)} (images in order)")
            jpegs += [_preview(p, request.kind) for p, _ in cands]
        try:
            picks = await vision_json(CHOOSER, "\n".join(lines) + "\n\nPick for each request. JSON only.", [j for j in jpegs if j],
                                      Picks, max_tokens=2000)
            calls = 1
        except Exception as exc:
            log.warning("Insert choice failed, inserts skipped: %s", exc)
            picks = Picks(picks=[])
        chosen = {p.request: p.candidate for p in picks.picks}
        for n, cands in pending:
            k = chosen.get(n, -1)
            if not 0 <= k < len(cands):
                continue
            path, licence = cands[k]
            _, _, request = placed[n]
            record = AssetRecord(kind=request.kind, scope="global", words=sorted(kit.words_of(request.query)),
                                 description=licence["title"][:300], licence=licence["licence"], source=licence["source"],
                                 made_by={"found_for": request.query, **licence})
            found[n] = await scout._keep(record, path)
    # Nothing free shows it: a generated photo (when switched on, a few per reel), then a 3D object from the kit
    # that literally shows it (or nothing), shown as a card.
    unresolved = [n for n, (_, _, request) in enumerate(placed) if request.kind != "footage" and n not in found]
    if unresolved and imagery.enabled():
        for n in unresolved[:get_settings().REEL_MAX_GENERATED_IMAGES]:
            request = placed[n][2]
            made = await imagery.generate(request.query, work / f"made_{n}.jpg")
            if made:
                record = AssetRecord(kind="photo", scope="global", words=sorted(kit.words_of(request.query)),
                                     description=f"Generated: {request.query}"[:300], source=get_settings().REEL_IMAGE_PROVIDER,
                                     made_by={"generated_for": request.query})
                found[n] = await scout._keep(record, made)
                placed[n] = (placed[n][0], placed[n][1], request.model_copy(update={"kind": "photo"}))
        unresolved = [n for n in unresolved if n not in found]
    if unresolved:
        from reel_engine import icons

        # A 3D object or an animated emoji that shows the thing (the director's "show" words, else its photo search).
        objects = await icons.choose([(getattr(placed[n][2], "show", "") or placed[n][2].query, placed[n][2].query + "; " + placed[n][2].why)
                                      for n in unresolved], animated=frozenset(range(len(unresolved))), kinds=("object3d",))
        calls += 1
        for n, asset in zip(unresolved, objects):
            if asset:
                found[n] = asset
                placed[n] = (placed[n][0], placed[n][1], placed[n][2].model_copy(update={"kind": "photo"}))
    out = []
    for n, (start, end, request) in enumerate(placed):
        if request.kind == "footage":
            if request.src not in sources:
                continue
            asset = AssetRef(id=f"src{request.src}", kind="footage", path=sources[request.src], licence="user footage", source="user")
        else:
            asset = found.get(n)
            if asset is None:
                continue
        # A kit object or emoji pops in beside the speaker; photos alternate full frame and card.
        style = "object" if asset.kind == "icon" else "card" if request.kind == "photo" and len(out) % 2 == 1 else "full"
        out.append(InsertItem(id=f"i{len(out)}", kind=request.kind, start=round(start, 3), end=round(end, 3), asset=asset,
                              label=request.label[:28], query=request.query, src_t0=max(0.0, request.at) if request.kind == "footage" else 0.0,
                              style=style))
    log.info("Inserts: %d placed (%d requested)", len(out), len(requests))
    return out, calls


def cutaway_cmd(item: InsertItem, out: Path, grade: Path, fps: int, width: int, height: int) -> list[str]:
    """A full-frame 9:16 cutaway of ``item``: a photo with a slow push, or a clip centre-cropped, graded to match."""
    length = item.end - item.start
    frames = max(1, round(length * fps))
    lut = str(grade).replace(":", "\\:")
    if item.kind == "photo":
        inputs = ["-loop", "1", "-t", f"{length + 0.2:.3f}", "-i", item.asset.path]
        chain = [f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2}",
                 f"zoompan=z='1.0+0.08*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps}"]
    else:
        inputs = ["-ss", f"{item.src_t0:.3f}", "-t", f"{length + 0.2:.3f}", "-i", item.asset.path]
        chain = [f"fps={fps}", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"]
    chain += [f"lut3d=file='{lut}'", "eq=contrast=1.04:saturation=1.08", "format=yuv420p"]
    return ["ffmpeg", "-v", "error", "-y", *inputs, "-an", "-vf", ",".join(chain), "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", INTERMEDIATE_PRESET, "-crf", "17", str(out)]


def overlay_cmd(picture: Path, cuts: list[tuple[InsertItem, Path]], out: Path) -> list[str]:
    chains, current = [], "0:v"
    for k, (item, _) in enumerate(cuts, start=1):
        chains.append(f"[{k}:v]setpts=PTS-STARTPTS+{item.start:.3f}/TB[c{k}]")
        chains.append(f"[{current}][c{k}]overlay=0:0:enable='between(t,{item.start:.3f},{item.end:.3f})':eof_action=pass[v{k}]")
        current = f"v{k}"
    return ["ffmpeg", "-v", "error", "-y", "-i", str(picture), *[a for _, p in cuts for a in ("-i", str(p))],
            "-filter_complex", ";".join(chains), "-map", f"[{current}]", "-c:v", "libx264", "-preset", INTERMEDIATE_PRESET, "-crf", "17", str(out)]

