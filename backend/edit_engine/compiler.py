"""The director's plan, turned into a frame-exact timeline.

The plan names sentences, shots and photos by ID; this module lays them out
in output time and enforces the editing rules the director is only asked to
follow: silences and fillers are cut, jump cuts alternate framing, B-roll is
capped and never covers the hook, pop-ups and sound effects are spaced out.

Three layouts, chosen by what the footage and script are:

* ``talking`` -- the creator speaks on camera; their words are the spine.
* ``voiceover`` -- a recorded or synthetic voiceover is the spine and every
  sentence gets a shot or photo.
* ``montage`` -- no speech: shots and photos cut to the music.

The result is plain JSON, the one document the browser preview plays and the
renderer draws. Everything here is pure; it has no I/O.
"""

from __future__ import annotations

from typing import Any

from transcription.language import is_hesitation

# Padding kept around speech at every cut, so a word's attack and decay survive
# (the same values content_intelligence.edit_plan uses for clips).
LEAD_PAD = 0.08
TAIL_PAD = 0.15
# Reels are tighter than long-form clips: a pause this long inside a sentence is cut.
JUMP_GAP = 0.35
MIN_PIECE = 0.3
PUNCH_ZOOM = 1.2
JUMP_ZOOM = 1.12
HOOK_SECONDS = 2.2
# The first line is the hook; B-roll never starts before this.
BROLL_NOT_BEFORE = 1.2
BROLL_MIN, BROLL_MAX = 1.2, 2.8
BROLL_SHARE = 0.4
BROLL_GAP = 1.5
POP_SECONDS = 1.1
POP_GAP = 3.5
SFX_GAP = 1.5
CARD_SECONDS = 2.0
# Beats each montage shot lasts, by energy; seconds when the track has no tempo.
MONTAGE_BEATS = {"low": 8, "medium": 4, "high": 2}
MONTAGE_FALLBACK_SECONDS = {"low": 2.6, "medium": 1.8, "high": 1.2}
MONTAGE_DEFAULT_SECONDS = 20.0
MUSIC_UNDER_VOICE_DB = -20.0
MUSIC_ALONE_DB = -8.0


def layout_for(mode: str, has_speech: bool) -> str:
    if mode == "voiceover":
        return "voiceover"
    return "talking" if has_speech else "montage"


def compile_timeline(analysis: dict[str, Any], plan: dict[str, Any], *, size: tuple[int, int],
                     target_seconds: int, max_seconds: int) -> dict[str, Any]:
    layout = plan.get("layout") or layout_for(plan.get("mode", "none"), bool(analysis.get("sentences")))
    builder = {"talking": _talking, "voiceover": _voiceover, "montage": _montage}[layout]
    timeline = builder(analysis, plan, target_seconds, max_seconds)
    timeline.update({
        "layout": layout, "width": size[0], "height": size[1], "fps": 30,
        "look": plan.get("look", "natural"), "caption_style": plan.get("caption_style", "hormozi"),
    })
    _add_hook(timeline, plan)
    if plan.get("mode") == "onscreen":
        _add_script_lines(timeline, [line["text"] for line in plan.get("script_lines") or []])
    timeline["sfx"] = _space_sfx(timeline["sfx"])
    timeline["music"] = _music(plan, timeline)
    timeline["picture"] = [_rounded(item) for item in timeline["picture"]]
    return timeline


# --- talking head -------------------------------------------------------------

def kept_sentences(analysis: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    """Sentence IDs in playing order, with the user's removals and restorations applied."""
    removed = set(plan.get("removed") or [])
    if plan.get("mode") == "spoken":
        order = [i for line in plan.get("script_lines") or [] for i in line["sentences"]]
        restored = [i for i in plan.get("restored") or [] if i not in order]
        order = _insert_by_time(order, restored, analysis["sentences"])
    else:
        order = list(plan.get("sentences") or [])
        known = set(order)
        order = _insert_by_time(order, [i for i in plan.get("restored") or [] if i not in known], analysis["sentences"])
    return [i for i in order if i not in removed]


def _insert_by_time(order: list[str], extra: list[str], sentences: list[dict[str, Any]]) -> list[str]:
    """``extra`` sentences placed after the kept sentence recorded just before each."""
    position = {s["id"]: n for n, s in enumerate(sentences)}
    result = list(order)
    for sid in sorted(extra, key=lambda i: position.get(i, 0)):
        before = [i for i in result if position.get(i, -1) < position.get(sid, 0)]
        at = result.index(max(before, key=lambda i: position[i])) + 1 if before else 0
        result.insert(at, sid)
    return result


def speech_pieces(words: list[dict[str, Any]]) -> list[tuple[float, float, list[dict[str, Any]]]]:
    """(start, end, words) runs of one sentence: fillers dropped, split at pauses over JUMP_GAP."""
    spoken = [w for w in words if not is_hesitation(str(w["word"]))]
    runs: list[list[dict[str, Any]]] = []
    for word in spoken:
        if runs and float(word["start"]) - float(runs[-1][-1]["end"]) <= JUMP_GAP:
            runs[-1].append(word)
        else:
            runs.append([word])
    pieces = []
    for index, run in enumerate(runs):
        before = runs[index - 1][-1] if index > 0 else None
        after = runs[index + 1][0] if index + 1 < len(runs) else None
        start = float(run[0]["start"]) - LEAD_PAD
        end = float(run[-1]["end"]) + TAIL_PAD
        # Pads never reach into the neighbouring words.
        if before is not None:
            start = max(start, (float(before["end"]) + float(run[0]["start"])) / 2)
        if after is not None:
            end = min(end, (float(run[-1]["end"]) + float(after["start"])) / 2)
        pieces.append((max(0.0, start), end, run))
    return [p for p in pieces if p[1] - p[0] >= MIN_PIECE]


def _shot_at(shots: list[dict[str, Any]], src: int, t: float) -> dict[str, Any] | None:
    return next((s for s in shots if s["src"] == src and s["start"] <= t < s["end"]), None)


def _talking(analysis: dict[str, Any], plan: dict[str, Any], target: int, max_seconds: int) -> dict[str, Any]:
    by_id = {s["id"]: s for s in analysis["sentences"]}
    words = analysis["words"]
    shots = analysis.get("shots") or []
    punch = set(plan.get("punch_ins") or [])
    order = kept_sentences(analysis, plan)
    cards = _missing_line_positions(plan) if plan.get("mode") == "spoken" else {}

    picture: list[dict[str, Any]] = []
    voice: list[dict[str, Any]] = []
    caption_words: list[dict[str, Any]] = []
    spans: dict[str, tuple[float, float]] = {}
    at, zoom, previous_end = 0.0, 1.0, None

    def add_card(text: str) -> None:
        nonlocal at, previous_end
        picture.append({"kind": "card", "text": text, "at": at, "dur": CARD_SECONDS})
        at += CARD_SECONDS
        previous_end = None

    for text in cards.get(0, []):
        add_card(text)
    for position, sid in enumerate(order):
        sentence = by_id.get(sid)
        if sentence is None:
            continue
        if at >= max_seconds or (target and plan.get("mode") != "spoken" and at >= target and position > 0):
            break
        first_piece = True
        sentence_start = at
        for start, end, run in speech_pieces(words[sentence["w0"]:sentence["w1"] + 1]):
            src = sentence["src"]
            if previous_end is not None and previous_end[0] == src and abs(previous_end[1] - start) > 0.05:
                zoom = 1.0 if zoom != 1.0 else JUMP_ZOOM
            piece_zoom = PUNCH_ZOOM if (first_piece and sid in punch) else zoom
            shot = _shot_at(shots, src, start)
            length = end - start
            picture.append({"kind": "video", "src": src, "in": start, "out": end, "at": at, "zoom": piece_zoom,
                            "crop_x": (shot or {}).get("face_x"), "brightness": (shot or {}).get("brightness")})
            voice.append({"src": src, "in": start, "out": end, "at": at})
            caption_words += [{"word": w["word"], "start": at + float(w["start"]) - start, "end": at + float(w["end"]) - start}
                              for w in run]
            at += length
            previous_end = (src, end)
            first_piece = False
        spans[sid] = (sentence_start, at)
        for text in cards.get(position + 1, []):
            add_card(text)

    duration = min(at, float(max_seconds))
    timeline = _base(clip_to(picture, duration), duration)
    timeline.update(voice=clip_to(voice, duration), words=[w for w in caption_words if w["start"] < duration])
    _add_broll(timeline, plan, analysis, spans)
    _add_pops(timeline, plan, spans)
    return timeline


def _missing_line_positions(plan: dict[str, Any]) -> dict[int, list[str]]:
    """Script lines never said on camera, keyed by how many kept sentences come before them."""
    positions: dict[int, list[str]] = {}
    count = 0
    for line in plan.get("script_lines") or []:
        if line["sentences"]:
            count += len(line["sentences"])
        elif not plan.get("skip_missing"):
            positions.setdefault(count, []).append(line["text"])
    return positions


def _add_broll(timeline: dict[str, Any], plan: dict[str, Any], analysis: dict[str, Any],
               spans: dict[str, tuple[float, float]]) -> None:
    shots = {s["id"]: s for s in analysis.get("shots") or []}
    photos = {p["id"]: p for p in analysis.get("photos") or []}
    budget = timeline["duration"] * BROLL_SHARE
    last_end = -BROLL_GAP
    for item in sorted(plan.get("broll") or [], key=lambda b: spans.get(b["sentence"], (1e9, 0))[0]):
        span = spans.get(item["sentence"])
        if span is None:
            continue
        start = max(span[0], BROLL_NOT_BEFORE)
        length = min(BROLL_MAX, span[1] - start, timeline["duration"] - start)
        if length < BROLL_MIN or start - last_end < BROLL_GAP or budget < length:
            continue
        visual = item["visual"]
        if visual in shots:
            shot = shots[visual]
            length = min(length, shot["end"] - shot["start"])
            if length < BROLL_MIN:
                continue
            offset = min(0.3, max(0.0, shot["end"] - shot["start"] - length))
            cover = {"kind": "video", "src": shot["src"], "in": shot["start"] + offset, "out": shot["start"] + offset + length,
                     "zoom": 1.0, "crop_x": shot.get("face_x"), "brightness": shot.get("brightness"), "broll": True}
        elif visual in photos:
            cover = {"kind": "image", "src": photos[visual]["src"], "dur": length}
        else:
            continue
        timeline["picture"] = overlay(timeline["picture"], cover, start, length)
        timeline["sfx"].append({"sound": "whoosh", "at": start})
        budget -= length
        last_end = start + length


def overlay(picture: list[dict[str, Any]], cover: dict[str, Any], start: float, length: float) -> list[dict[str, Any]]:
    """``picture`` with ``cover`` shown over [start, start + length); items underneath are trimmed or split."""
    end = start + length
    result: list[dict[str, Any]] = []
    for item in picture:
        item_end = item["at"] + _length(item)
        if item_end <= start or item["at"] >= end:
            result.append(item)
            continue
        if item["at"] < start:
            result.append(_trimmed(item, item["at"], start))
        if item_end > end:
            result.append(_trimmed(item, end, item_end))
    result.append({**cover, "at": start, **({"dur": length} if cover["kind"] != "video" else {})})
    return sorted(result, key=lambda i: i["at"])


def clip_to(items: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """Items that start before ``duration``, the last one cut to end there."""
    kept = []
    for item in items:
        if item["at"] >= duration - 0.01:
            continue
        end = item["at"] + _length(item)
        kept.append(_trimmed(item, item["at"], duration) if end > duration else item)
    return kept


def _length(item: dict[str, Any]) -> float:
    """Seconds an item plays: source span for footage and voice, ``dur`` for stills and cards."""
    return item["out"] - item["in"] if "in" in item else item["dur"]


def _trimmed(item: dict[str, Any], new_at: float, new_end: float) -> dict[str, Any]:
    if "in" in item:
        offset = new_at - item["at"]
        return {**item, "at": new_at, "in": item["in"] + offset, "out": item["in"] + offset + (new_end - new_at)}
    return {**item, "at": new_at, "dur": new_end - new_at}


def _add_pops(timeline: dict[str, Any], plan: dict[str, Any], spans: dict[str, tuple[float, float]]) -> None:
    last = HOOK_SECONDS - POP_GAP
    for pop in sorted(plan.get("pops") or [], key=lambda p: spans.get(p["sentence"], (1e9, 0))[0]):
        span = spans.get(pop["sentence"])
        if span is None:
            continue
        at = span[0] + 0.15
        if at - last < POP_GAP or at + POP_SECONDS > timeline["duration"]:
            continue
        timeline["texts"].append({"kind": "pop", "text": pop["text"], "at": at, "dur": POP_SECONDS})
        timeline["sfx"].append({"sound": "pop", "at": at})
        last = at


# --- voiceover ----------------------------------------------------------------

def _voiceover(analysis: dict[str, Any], plan: dict[str, Any], target: int, max_seconds: int) -> dict[str, Any]:
    sentences = analysis.get("voice_sentences") or []
    words = analysis.get("voice_words") or []
    duration = min(float(max_seconds), (float(words[-1]["end"]) + 0.4) if words else 0.0)
    assigned = {b["sentence"]: b["visual"] for b in plan.get("broll") or []}
    pool = _visual_pool(analysis, plan)
    picture: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences):
        start = 0.0 if index == 0 else float(sentence["start"])
        end = float(sentences[index + 1]["start"]) if index + 1 < len(sentences) else duration
        end = min(end, duration)
        if end - start <= 0.05:
            continue
        visual = assigned.get(sentence["id"]) or (pool[index % len(pool)] if pool else None)
        picture += _fill(visual, analysis, start, end - start)
    timeline = _base(picture or [{"kind": "card", "text": plan.get("hook") or "", "at": 0.0, "dur": duration}], duration)
    timeline.update(voice=[], words=[{"word": w["word"], "start": float(w["start"]), "end": float(w["end"])}
                                     for w in words if float(w["start"]) < duration])
    if analysis.get("voiceover_src") is not None:
        timeline["voiceover"] = {"src": analysis["voiceover_src"]}
    return timeline


def _visual_pool(analysis: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    return list(plan.get("montage") or []) or [s["id"] for s in analysis.get("shots") or [] if s.get("usable")] \
        + [p["id"] for p in analysis.get("photos") or []]


def _fill(visual: str | None, analysis: dict[str, Any], at: float, length: float) -> list[dict[str, Any]]:
    """Picture items showing ``visual`` for ``length`` seconds; a short shot repeats from its start."""
    shots = {s["id"]: s for s in analysis.get("shots") or []}
    photos = {p["id"]: p for p in analysis.get("photos") or []}
    if visual in photos:
        return [{"kind": "image", "src": photos[visual]["src"], "at": at, "dur": length}]
    if visual not in shots:
        return [{"kind": "card", "text": "", "at": at, "dur": length}]
    shot, items, t = shots[visual], [], at
    while t < at + length - 0.01:
        piece = min(shot["end"] - shot["start"], at + length - t)
        items.append({"kind": "video", "src": shot["src"], "in": shot["start"], "out": shot["start"] + piece, "at": t,
                      "zoom": 1.0, "crop_x": shot.get("face_x"), "brightness": shot.get("brightness")})
        t += piece
    return items


# --- montage ------------------------------------------------------------------

def _montage(analysis: dict[str, Any], plan: dict[str, Any], target: int, max_seconds: int) -> dict[str, Any]:
    bpm = (plan.get("music") or {}).get("bpm")
    energy = plan.get("energy", "medium")
    unit = 60.0 / bpm * MONTAGE_BEATS.get(energy, 4) if bpm else MONTAGE_FALLBACK_SECONDS.get(energy, 1.8)
    goal = min(float(max_seconds), float(target) if target else MONTAGE_DEFAULT_SECONDS)
    shots = {s["id"]: s for s in analysis.get("shots") or []}
    picture: list[dict[str, Any]] = []
    at = 0.0
    for visual in _visual_pool(analysis, plan):
        if at >= goal - 0.3:
            break
        available = (shots[visual]["end"] - shots[visual]["start"]) if visual in shots else unit
        # Cuts land on the beat, unless a shot is too short to last one unit.
        length = min(goal - at, unit, available)
        if length < 0.5:
            continue
        picture += _fill(visual, analysis, at, length)
        at += length
    timeline = _base(picture, at)
    timeline.update(voice=[], words=[])
    return timeline


# --- shared -------------------------------------------------------------------

def _base(picture: list[dict[str, Any]], duration: float) -> dict[str, Any]:
    return {"duration": round(duration, 3), "picture": picture, "voice": [], "voiceover": None, "texts": [],
            "words": [], "sfx": [], "music": None}


def _add_hook(timeline: dict[str, Any], plan: dict[str, Any]) -> None:
    hook = (plan.get("hook") or "").strip()
    if hook and timeline["duration"] > 0:
        timeline["texts"].insert(0, {"kind": "hook", "text": hook, "at": 0.0, "dur": min(HOOK_SECONDS, timeline["duration"])})
        timeline["sfx"].insert(0, {"sound": "hit", "at": 0.0})


def _add_script_lines(timeline: dict[str, Any], lines: list[str]) -> None:
    """On-screen script: each line shown in turn across the reel, after the hook."""
    start = min(HOOK_SECONDS, timeline["duration"])
    if not lines or timeline["duration"] - start < 1.0:
        return
    each = (timeline["duration"] - start) / len(lines)
    for index, line in enumerate(lines):
        timeline["texts"].append({"kind": "line", "text": line, "at": start + index * each, "dur": each})
    # Spoken captions would fight the script text for the same space.
    timeline["words"] = []


def _space_sfx(sfx: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spaced: list[dict[str, Any]] = []
    for cue in sorted(sfx, key=lambda c: c["at"]):
        if not spaced or cue["at"] - spaced[-1]["at"] >= SFX_GAP:
            spaced.append({**cue, "at": round(cue["at"], 3)})
    return spaced


def _music(plan: dict[str, Any], timeline: dict[str, Any]) -> dict[str, Any] | None:
    music = plan.get("music")
    if not music or not music.get("track_id") or timeline["duration"] <= 0:
        return None
    has_voice = bool(timeline["voice"] or timeline.get("voiceover"))
    return {"track_id": music["track_id"], "offset": 0.0,
            "gain_db": MUSIC_UNDER_VOICE_DB if has_voice else MUSIC_ALONE_DB, "duck": has_voice}


def _rounded(item: dict[str, Any]) -> dict[str, Any]:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in item.items()}


def summary(timeline: dict[str, Any]) -> dict[str, int]:
    """Counts the plan card shows."""
    broll = [p for p in timeline["picture"] if p.get("broll") or p["kind"] == "image"]
    return {
        "broll": len(broll),
        "pops": sum(1 for t in timeline["texts"] if t["kind"] == "pop"),
        "cuts": max(0, len(timeline["picture"]) - 1),
    }
