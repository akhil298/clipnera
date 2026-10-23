"""Compile: the director's story becomes exact tracks, with every value checked.

- Video: talking clips are tightened (fillers and pauses over 0.35 s cut, voice never sped up, jump cuts
  covered by alternating framing); picture clips get speeds (fast-forward repetitive work, slow motion on
  money shots), quantized to the score's beat.
- Graphics: each beat is mapped from its words or moment to output time, given its template data, kept
  only if its anchor survived the cut, and spaced so two never share the screen; sections become chapter
  cards and a progress bar; the hook, title and CTA are added.
- Captions: lines of 2-4 kept words with one big keyword, quiet under full-screen cards; a named thing's
  icon moves into its caption instead of a separate tag (one graphic at a time).
"""

from __future__ import annotations

from reel_engine.director import DirectorPlan, recipe
from reel_engine.plan import AudioReport, Brief, CaptionLine, GraphicItem, Section, Shot, VideoItem, Word

SCORE_BPM = 112
BEAT = 60 / SCORE_BPM
FPS = 30
MAX_GAP = 0.35
PAD_IN, PAD_OUT = 0.06, 0.1
MIN_SPEED, MAX_SPEED = 0.55, 2.8
MONEY_SPEED = 0.65
MONTAGE_SECONDS = round(BEAT / 2 * FPS) / FPS
MIN_GRAPHIC, MAX_GRAPHIC = 1.2, 3.5
CARD_KINDS = {"statement", "list", "chart", "flow", "count_up"}
VOICE_KINDS = ("voice", "voice_song")
LINE_WORDS = 4
CARD_EVERY = 10.0
# Titles and chapters in a style that contrasts with the captions' (still one family).
TITLE_PAIR = {"punch": "editorial", "editorial": "editorial", "neon": "neon", "highlight": "punch", "bubble": "script",
              "script": "bubble", "comic": "comic", "minimal": "editorial"}
# Graphics that hold the eye: a caption steps aside while one is on screen.
CAPTION_YIELDS_TO = {"two", "keyword", "count_up", "statement", "list", "flow", "chart", "cta", "flicker", "photocard"}
# Never the big word of a caption line.
WEAK = {"a", "an", "the", "and", "but", "or", "so", "to", "of", "in", "on", "at", "it", "is", "was", "be", "we", "we've", "i",
        "i'm", "you", "your", "they", "he", "she", "this", "that", "with", "for", "do", "did", "not", "just", "very", "really",
        "um", "uh", "like", "have", "has", "had", "are", "were", "our", "my", "me", "up", "all", "any", "going", "as", "you're",
        "that's", "it's", "get", "got", "try", "think", "what", "will", "can", "would", "could", "should", "there", "here", "then",
        "than", "about", "into", "from", "by", "if", "when", "how", "kind", "lot", "thing", "things", "actually", "first", "ago"}


# ------------------------------------------------------------------ brief

def brief_of(d: DirectorPlan, audio: AudioReport, target: float) -> tuple[Brief, str]:
    """The path follows the measured audio; when the director disagrees, the safer reading wins and is noted."""
    measured = audio.kind
    note = ""
    if (measured in VOICE_KINDS) != (d.audio_view in VOICE_KINDS):
        if measured in VOICE_KINDS and audio.lyrics:
            measured = "song"
        note = f"Listen measured {audio.kind}, the director heard {d.audio_view}; edited as {measured}."
    path = "voice" if measured in VOICE_KINDS else "visual"
    r = recipe(d.recipe)
    caption_mode = d.caption_mode if path == "voice" else "none"
    music = d.music if d.music != "none" else r["music"]
    if path == "visual":
        music = "score"
    brief = Brief(path=path, audio_kind=measured, recipe=r["id"], target_seconds=target or d.target_seconds,
                  text_style=d.text_style, title_style=TITLE_PAIR.get(d.text_style, d.text_style),
                  title_lead=d.title_lead, title_text=d.title_text,
                  hook_word=(d.hooks[0].word if d.hooks else "").upper()[:12],
                  caption_mode=caption_mode, music=music, mood=d.mood, accent=r["accent"],
                  sections=[Section(**sec.model_dump()) for sec in d.sections[:5]], cta=d.cta[:34], notes=(d.notes + (" " + note if note else "")).strip())
    return brief, note


# ------------------------------------------------------------------ video

def _talk_spans(words: list[Word], w0: int, w1: int, src_len: dict[int, float]) -> list[tuple[int, float, float, int, int]]:
    """(src, start, end, first word, last word) runs of kept speech inside w0..w1: fillers and long pauses cut."""
    spans: list[list] = []
    for w in words[max(0, w0):min(len(words), w1 + 1)]:
        if w.filler:
            continue
        if spans and spans[-1][0] == w.src and w.t0 - spans[-1][2] <= MAX_GAP:
            spans[-1][2], spans[-1][4] = w.t1, w.i
        else:
            spans.append([w.src, w.t0, w.t1, w.i, w.i])
    return [(s, max(0.0, a - PAD_IN), min(src_len.get(s, b + PAD_OUT), b + PAD_OUT), i0, i1) for s, a, b, i0, i1 in spans]


def _beats(seconds: float, beat: float = BEAT) -> float:
    return max(0.5, round(seconds / beat * 2) / 2)


def video_track(d: DirectorPlan, brief: Brief, words: list[Word], shots: list[Shot], src_len: dict[int, float],
                hook_index: int = 0, beat: float = BEAT) -> list[VideoItem]:
    """The video track; picture clips are cut to whole half-beats of ``beat`` (the music's) from the start."""
    clips = list(d.story)
    if d.hooks:
        hook = d.hooks[min(hook_index, len(d.hooks) - 1)].clip
        clips = [hook.model_copy(update={"role": "hook", "zoom": "punch"})] + [c for c in clips if c.role != "hook"]
    shot_seconds = recipe(brief.recipe)["shot_seconds"]
    items: list[VideoItem] = []
    flip = False
    for n, clip in enumerate(clips):
        section = clip.section if 0 <= clip.section < len(brief.sections) else -1
        if brief.path == "voice" and clip.w0 >= 0 and clip.w1 >= clip.w0 and words:
            for k, (src, a, b, _, _) in enumerate(_talk_spans(words, clip.w0, clip.w1, src_len)):
                if b - a < 0.25:
                    continue
                zoom = clip.zoom if k == 0 else ("in" if flip else "out")
                flip = not flip
                items.append(VideoItem(id=f"v{len(items)}", src=src, t0=round(a, 3), t1=round(b, 3), zoom=zoom, role=clip.role,
                                       section=section if k == 0 else -1, sound=clip.sound, money=clip.money, what=clip.what,
                                       keeps_voice=True))
            continue
        if clip.src not in src_len or clip.start < 0:
            continue
        start = min(max(0.0, clip.start), max(0.0, src_len[clip.src] - 0.3))
        end = min(src_len[clip.src], max(clip.end, start + 0.3))
        length = end - start
        if clip.role == "montage":
            out_len = round(beat / 2 * FPS) / FPS
            end = min(src_len[clip.src], start + out_len)
            length = end - start
        elif clip.money:
            out_len = beat * _beats(min(length / MONEY_SPEED, 3.2), beat)
        else:
            out_len = beat * _beats(min(length, max(shot_seconds, length / MAX_SPEED)), beat)
        speed = min(MAX_SPEED, max(MIN_SPEED, length / out_len)) if out_len else 1.0
        items.append(VideoItem(id=f"v{len(items)}", src=clip.src, t0=round(start, 3), t1=round(start + speed * out_len, 3),
                               speed=round(speed, 4), zoom=clip.zoom, role=clip.role, section=section, sound=clip.sound,
                               money=clip.money, what=clip.what))
    t = 0.0
    for item in items:
        length = round((item.t1 - item.t0) / item.speed * FPS) / FPS
        item.out0, item.out1 = round(t, 3), round(t + length, 3)
        t += length
    return items


def to_output(items: list[VideoItem], src: int, t: float) -> float | None:
    """Output second of source second ``t`` of ``src``, or None when that moment was cut."""
    for item in items:
        if item.src == src and item.t0 - 0.02 <= t <= item.t1 + 0.02:
            return round(item.out0 + max(0.0, t - item.t0) / item.speed, 3)
    return None


# ------------------------------------------------------------------ graphics

def _word_times(items: list[VideoItem], words: list[Word], w0: int, w1: int) -> tuple[float, float] | None:
    if not (0 <= w0 < len(words)):
        return None
    start = to_output(items, words[w0].src, words[w0].t0)
    last = words[min(max(w1, w0), len(words) - 1)]
    end = to_output(items, last.src, last.t1)
    if start is None:
        return None
    return start, end if end is not None and end > start else start + MIN_GRAPHIC


def _steps(items: list[VideoItem], words: list[Word], w0: int, w1: int, labels: list[str], start: float, end: float) -> list[float]:
    """When each list item lands: the output time of the first word that starts it, else evenly spaced."""
    found = []
    pool = words[max(0, w0):min(len(words), w1 + 1)]
    for label in labels:
        head = (label.split() or [""])[0].lower().strip(".,!?")
        hit = next((w for w in pool if w.text.lower().strip(".,!?") == head), None)
        t = to_output(items, hit.src, hit.t0) if hit else None
        found.append(None if t is None else t - start)
    if any(v is None for v in found) or found != sorted(found):
        gap = max(0.3, (end - start - 0.4) / max(1, len(labels)))
        return [round(0.2 + k * gap, 3) for k in range(len(labels))]
    return [round(max(0.05, v), 3) for v in found]


def _shot_at(shots: list[Shot], items: list[VideoItem], out_t: float) -> Shot | None:
    item = next((i for i in items if i.out0 <= out_t < i.out1), None)
    if item is None:
        return None
    src_t = item.t0 + (out_t - item.out0) * item.speed
    return next((s for s in shots if s.src == item.src and s.t0 <= src_t < s.t1), None)


def graphics_track(d: DirectorPlan, brief: Brief, words: list[Word], items: list[VideoItem], shots: list[Shot]) -> list[GraphicItem]:
    out: list[GraphicItem] = []
    total = items[-1].out1 if items else 0.0

    def add(kind: str, start: float, end: float, data: dict, place: str = "beside", icon: str = "", why: str = "",
            by: str = "graphics", steps: list[float] | None = None) -> None:
        end = min(end, total)
        if end - start < (0.25 if kind == "wash" else 0.5):
            return
        shot = _shot_at(shots, items, start + 0.1)
        out.append(GraphicItem(id=f"g{len(out)}", kind=kind, start=round(start, 3), end=round(end, 3),
                               data={**data, **({"steps": steps} if steps else {}), **({"icon_query": icon} if icon else {})},
                               place=place, behind=place == "behind", shot=shot.id if shot else "", why=why, by=by))

    hook = next((i for i in items if i.role == "hook"), None)
    # A reel in chapters (three recipes, five tips) opens on its title; a single idea opens on one huge word.
    title_first = bool(hook and brief.title_text and len(brief.sections) >= 2)
    if hook and title_first:
        add("two", hook.out0 + 0.15, min(hook.out1 + 0.4, hook.out0 + 2.6), {"lead": brief.title_lead, "text": brief.title_text},
            icon="sparkles", why="hook word", by="finish")
    elif hook and brief.hook_word:
        add("keyword", hook.out0, min(hook.out1, hook.out0 + 2.4), {"text": brief.hook_word, "lead": ""}, place="behind", why="hook word")
    starts = {}
    for item in items:
        if item.section >= 0 and item.section not in starts:
            starts[item.section] = item
    for n, item in sorted(starts.items()):
        sec = brief.sections[n]
        add("wash", item.out0 - 0.08, item.out0 + 0.26, {}, place="card", why="step transition", by="camera")
        add("chapter", item.out0 + 0.05, min(item.out1, item.out0 + 1.8), {"num": f"{n + 1:02d}", "lead": sec.lead, "text": sec.text},
            icon=sec.icon, why="step opens")
    if len(starts) >= 3:
        first, last_step = min(i.out0 for i in starts.values()), max(i.out1 for i in items if i.role in ("step", "body", "montage") or i.section >= 0)
        order = sorted(starts)
        add("progress", first, last_step, {"steps": [brief.sections[n].short[:8] for n in order],
                                            "at": [round(starts[n].out0 - first, 3) for n in order]}, place="top", why="progress")
    montage = [i for i in items if i.role == "montage"]
    if montage:
        add("flicker", montage[0].out0, montage[-1].out1,
            {"items": [{"text": (i.what.split() or [""])[0][:12], "at": round(i.out0 - montage[0].out0, 3)} for i in montage]},
            place="card", why="montage words")
    for beat in d.beats:
        if beat.w0 >= 0:
            span = _word_times(items, words, beat.w0, beat.w1)
        else:
            a = to_output(items, beat.src, beat.at)
            b = to_output(items, beat.src, beat.until) if beat.until > beat.at else None
            span = (a, b if b and b > a else a + 1.6) if a is not None else None
        if span is None:
            continue
        start, end = span
        end = min(max(end + 0.5, start + MIN_GRAPHIC), start + MAX_GRAPHIC)
        k = beat.kind
        if k == "two":
            add("two", start, end, {"lead": beat.lead, "text": beat.text}, icon=beat.icon, why=beat.why)
        elif k == "tag":
            add("tag", start, end, {"text": beat.text}, icon=beat.icon, why=beat.why)
        elif k == "list":
            items_ = [i for i in beat.items if i][:5]
            if items_:
                end = max(end, start + 0.6 * len(items_) + 0.8)
                add("list", start, end, {"title": beat.lead, "items": items_, "mark": beat.mark}, place="panel", why=beat.why,
                    steps=_steps(items, words, beat.w0, beat.w1, items_, start, end))
        elif k == "count_up":
            add("count_up", start, max(end, start + 1.8), {"prefix": beat.prefix, "number": beat.number or "0", "suffix": beat.suffix,
                                                          "label": beat.text}, why=beat.why)
        elif k == "keyword":
            shot = _shot_at(shots, items, start + 0.1)
            add("keyword", start, end, {"text": beat.text.upper(), "lead": beat.lead}, place="behind" if shot and shot.faces else "beside",
                why=beat.why)
        elif k == "statement":
            add("statement", start, end, {"text": beat.text, "label": beat.lead}, place="card", why=beat.why)
        elif k == "chart":
            add("chart", start, max(end, start + 2.0), {"label": beat.text, "trend": beat.trend if beat.trend != "none" else "up",
                                                       "figures": [beat.number] if beat.number else []}, place="panel", why=beat.why)
        elif k == "flow":
            items_ = [i for i in beat.items if i][:5]
            if items_:
                add("flow", start, max(end, start + 0.6 * len(items_) + 0.8), {"items": items_}, place="panel", why=beat.why,
                    steps=_steps(items, words, beat.w0, beat.w1, items_, start, end))
        elif k == "name":
            add("name", start, end, {"text": beat.text, "label": beat.lead}, why=beat.why)
    payoff = next((i for i in items if i.role == "payoff"), None) or (items[-2] if len(items) > 2 else None)
    if payoff and brief.title_text and not title_first:
        add("two", payoff.out0 + 0.1, min(payoff.out1, payoff.out0 + 2.6), {"lead": brief.title_lead, "text": brief.title_text},
            icon="sparkles", why="title over the payoff", by="finish")
    if items and brief.cta:
        last = items[-1]
        add("cta", max(last.out0, last.out1 - 2.2), last.out1 - 0.05, {"verb": brief.cta.upper(), "text": ""}, why="call to action", by="finish")
    out = _space(out)
    if brief.path == "voice":
        out = _few_cards(out, total)
    return out


def _few_cards(graphics: list[GraphicItem], total: float) -> list[GraphicItem]:
    """A talking reel keeps the speaker on screen: at most one full-screen card per CARD_EVERY seconds."""
    allowed = max(1, int(total // CARD_EVERY))
    cards = [g for g in graphics if g.place == "card" and g.kind not in ("wash", "flicker")]
    keep = set(id(g) for g in sorted(cards, key=lambda g: (g.why == "", g.start))[:allowed])
    return [g for g in graphics if not (g.place == "card" and g.kind not in ("wash", "flicker")) or id(g) in keep]


def _space(graphics: list[GraphicItem]) -> list[GraphicItem]:
    """One story graphic on screen at a time. Washes and the progress bar always stay; then chapters and the hook
    word, the title and CTA, and the beats in time order, each shifted past a clash or dropped if too little is left."""
    pinned = [g for g in graphics if g.kind in ("wash", "progress")]
    rank = {"chapter": 0}
    order = sorted((g for g in graphics if g not in pinned),
                   key=lambda g: (0 if g.kind in rank or g.why == "hook word" else 1 if g.by == "finish" else 2, g.start))
    keep, taken = list(pinned), []
    for g in order:
        clash = [b for a, b in taken if a < g.end and g.start < b]
        if clash:
            free = max(clash) + 0.05
            if g.end - free < 0.9:
                continue
            g.start = round(free, 3)
        keep.append(g)
        taken.append((g.start, g.end))
    keep.sort(key=lambda g: g.start)
    for n, g in enumerate(keep):
        g.id = f"g{n}"
    return keep


# ------------------------------------------------------------------ captions

def captions_track(d: DirectorPlan, brief: Brief, words: list[Word], items: list[VideoItem],
                   graphics: list[GraphicItem]) -> tuple[list[CaptionLine], list[GraphicItem]]:
    if brief.caption_mode == "none" or not words:
        return [], graphics
    keywords = set(d.keywords)
    kept: list[tuple[Word, float, float]] = []
    for item in items:
        if not item.keeps_voice:
            continue
        for w in words:
            if w.src == item.src and not w.filler and item.t0 <= w.t0 < item.t1:
                kept.append((w, round(item.out0 + (w.t0 - item.t0), 3), round(item.out0 + (min(w.t1, item.t1) - item.t0), 3)))
    # A stutter ("and and") shows once.
    kept = [e for k, e in enumerate(kept) if k == 0 or e[0].text.lower().strip(",.") != kept[k - 1][0].text.lower().strip(",.")]
    lines: list[list[tuple[Word, float, float]]] = []
    for entry in kept:
        w, a, _ = entry
        if lines:
            prev = lines[-1][-1]
            if len(lines[-1]) < LINE_WORDS and a - prev[2] < 0.45 and not prev[0].text.rstrip().endswith((".", "?", "!", ",")):
                lines[-1].append(entry)
                continue
        lines.append([entry])
    cards = [(g.start, g.end) for g in graphics if g.kind in CARD_KINDS or g.place == "card" or g.kind in CAPTION_YIELDS_TO]
    tags = [g for g in graphics if g.kind == "tag"]
    out: list[CaptionLine] = []
    used_tags: set[str] = set()
    for n, line in enumerate(lines):
        start = line[0][1]
        end = min(line[-1][2] + 0.5, lines[n + 1][0][1]) if n + 1 < len(lines) else line[-1][2] + 0.5
        ids = {w.i for w, _, _ in line}
        if d.drop_word in ids:
            # The payoff line is the reel's big moment: a card still up when it starts ends there.
            for g in graphics:
                if (g.kind in CARD_KINDS or g.place == "card") and g.start < start < g.end:
                    g.end = round(max(g.start + 0.6, start - 0.05), 3)
            cards = [(g.start, g.end) for g in graphics if g.kind in CARD_KINDS or g.place == "card" or g.kind in CAPTION_YIELDS_TO]
        if any(a < end and start < b for a, b in cards):
            continue
        if brief.caption_mode == "keyword" and not (ids & keywords) and d.drop_word not in ids:
            continue
        strong = [w for w, _, _ in line if w.text.lower().strip(".,!?'\"") not in WEAK]
        # A line of only small words ("up here") gets no big word at all.
        key = next((w for w, _, _ in line if w.i in keywords), None) or (max(strong, key=lambda w: len(w.text)) if strong else None)
        lead = " ".join(w.text for w, _, _ in line if w is not key)
        spoken = [{"text": w.text, "key": w is key, "at": round(max(0.0, a - start), 3)} for w, a, _ in line]
        tag = next((t for t in tags if t.start < end and start < t.end and t.id not in used_tags), None)
        icon_query = ""
        if tag:
            used_tags.add(tag.id)
            icon_query = tag.data.get("icon_query", "")
        payoff = d.drop_word in ids
        if payoff and not icon_query:
            icon_query = "sparkles"
        out.append(CaptionLine(id=f"c{len(out)}", start=round(start, 3), end=round(end, 3), lead=lead, keyword=key.text if key else "",
                               words=spoken, icon_query=icon_query, payoff=payoff))
    graphics = [g for g in graphics if g.id not in used_tags]
    return out, graphics
