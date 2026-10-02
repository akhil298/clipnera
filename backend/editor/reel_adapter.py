"""A footage reel's compiled timeline (edit_engine.compiler, float seconds) as a Timeline v1.

This is how a reel opens in the editor: the compiled picture, voice, texts,
sound effects and music become tracks and items, sources become assets, and
every time is snapped to whole frames. Item boundaries are rounded once, from
the reel's own start and end times, so neighbouring pieces still meet exactly.
"""

from __future__ import annotations

from typing import Any

from editor.timeline import (
    Asset,
    Captions,
    ClipItem,
    MusicItem,
    SfxItem,
    TextItem,
    Timeline,
    Track,
    Transform,
    check,
    to_frames,
)

FPS = 30
# Reel sound effects are one-shot cues with no length; this covers the longest of them.
SFX_SECONDS = 0.5
_ASSET_KINDS = {"video": "video", "image": "image", "voice": "audio"}
# Each kind of on-screen text gets its own track, since a card can share a moment with the hook.
_TEXT_TRACKS = {"hook": "hook", "pop": "pops", "line": "lines"}


def from_reel(compiled: dict[str, Any], sources: list[dict[str, Any]], *, caption_style: str,
              language: str, size: tuple[int, int]) -> Timeline:
    """Convert one compiled reel. ``sources`` is the reel's source list, indexed by each item's ``src``."""
    assets = {_asset_id(i): _asset(i, source) for i, source in enumerate(sources)}
    tracks = [
        Track(id="v1", kind="video", items=_picture(compiled.get("picture") or [], assets)),
        _text_track("cards", [{"kind": "card", **p} for p in compiled.get("picture") or [] if p["kind"] == "card"]),
        *(_text_track(track_id, [t for t in compiled.get("texts") or [] if t["kind"] == kind])
          for kind, track_id in _TEXT_TRACKS.items()),
        Track(id="voice", kind="audio", items=_voice(compiled, assets)),
        Track(id="sfx", kind="audio", items=[
            SfxItem(type="sfx", id=f"fx{i}", name=cue["sound"], at=_frame(cue["at"]), dur=_frame(SFX_SECONDS))
            for i, cue in enumerate(compiled.get("sfx") or [])
        ]),
        Track(id="music", kind="audio", items=_music(compiled)),
    ]
    tracks = [track for track in tracks if track.items or track.id == "v1"]
    has_speech = bool(compiled.get("words")) and any(t.id == "voice" for t in tracks)
    timeline = Timeline(
        fps=FPS, width=size[0], height=size[1], look=compiled.get("look") or "natural", assets=assets, tracks=tracks,
        captions=Captions(style=caption_style, language=language, follow="voice") if has_speech else None,
    )
    check(timeline)
    return timeline


def _frame(seconds: float) -> int:
    return to_frames(float(seconds) * FPS)


def _bounds(at: float, length: float) -> tuple[int, int]:
    """Start and end rounded separately, so adjacent pieces share a boundary frame."""
    return _frame(at), _frame(at + length)


def _asset_id(index: int) -> str:
    return f"s{index}"


def _asset(index: int, source: dict[str, Any]) -> Asset:
    kind = _ASSET_KINDS[source["kind"]]
    return Asset(
        id=_asset_id(index), kind=kind, key=source["key"], proxy=source.get("proxy_key"),
        frames=1 if kind == "image" else max(1, to_frames(float(source["duration"]) * FPS)),
        width=source.get("width"), height=source.get("height"),
        has_audio=kind == "audio" or bool(source.get("has_audio")),
    )


def _clip(item_id: str, asset: Asset, start: int, end: int, src_in: int, transform: Transform | None = None) -> ClipItem | None:
    """A clip covering ``start``..``end``, shortened if rounding ran it past its source's last frame."""
    length = end - start
    if asset.kind != "image":
        length = min(length, asset.frames - src_in)
    if length <= 0:
        return None
    return ClipItem(type="clip", id=item_id, asset=asset.id, at=start, src_in=src_in, src_out=src_in + length,
                    transform=transform or Transform())


def _picture(picture: list[dict[str, Any]], assets: dict[str, Asset]) -> list[ClipItem]:
    items: list[ClipItem] = []
    for i, piece in enumerate(picture):
        if piece["kind"] == "card":
            continue
        length = piece["out"] - piece["in"] if piece["kind"] == "video" else piece["dur"]
        start, end = _bounds(piece["at"], length)
        src_in = _frame(piece["in"]) if piece["kind"] == "video" else 0
        transform = Transform(x=piece.get("crop_x") if piece.get("crop_x") is not None else 0.5,
                              scale=piece.get("zoom") or 1.0)
        clip = _clip(f"p{i}", assets[_asset_id(piece["src"])], start, end, src_in, transform)
        if clip is not None:
            items.append(clip)
    return items


def _voice(compiled: dict[str, Any], assets: dict[str, Asset]) -> list[ClipItem]:
    voiceover = compiled.get("voiceover")
    if voiceover:
        asset = assets[_asset_id(voiceover["src"])]
        clip = _clip("vo", asset, 0, _frame(compiled["duration"]), 0)
        return [clip] if clip else []
    pieces = (_clip(f"a{i}", assets[_asset_id(p["src"])], *_bounds(p["at"], p["out"] - p["in"]), _frame(p["in"]))
              for i, p in enumerate(compiled.get("voice") or []))
    return [clip for clip in pieces if clip is not None]


def _text_track(track_id: str, texts: list[dict[str, Any]]) -> Track:
    items = []
    for i, text in enumerate(texts):
        start, end = _bounds(text["at"], text["dur"])
        if end > start and text.get("text"):
            items.append(TextItem(type="text", id=f"{track_id}{i}", text=text["text"][:200], style=text["kind"],
                                  at=start, dur=end - start))
    return Track(id=track_id, kind="text", items=items)


def _music(compiled: dict[str, Any]) -> list[MusicItem]:
    music = compiled.get("music")
    total = _frame(compiled.get("duration") or 0)
    if not music or total <= 0:
        return []
    return [MusicItem(type="music", id="music0", track=music["track_id"], at=0, dur=total,
                      offset=_frame(music.get("offset") or 0), gain_db=music["gain_db"], duck=music["duck"])]
