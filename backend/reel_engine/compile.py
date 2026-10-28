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

from reel_engine import styles, typekits
from reel_engine.director import DClip, DirectorPlan, recipe
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
HOOK_SECONDS = 3.2
CARD_KINDS = {"statement", "list", "chart", "flow", "count_up"}
VOICE_KINDS = ("voice", "voice_song")
MIN_LINE_WORDS = 3
CARD_EVERY = 8.0
# Designed graphics (motion_code.py): at most this many a reel, at least this long, held this long past the last word.
MAX_DESIGNS, MIN_DESIGN, DESIGN_TAIL = 3, 1.2, 0.35
EMOJI_EVERY = 3
# Graphics that hold the eye: a keyword caption steps aside while one is on screen.
CAPTION_YIELDS_TO = {"two", "keyword", "count_up", "statement", "list", "flow", "chart", "cta", "flicker", "photocard"}
# Every-word captions carry the speech: they give way to graphics that take the whole frame, and under a word
# graphic they leave out only the words it already shows.
# Captions give way to these entirely: a full card, or the hook headline (while it is up, it is the reel's text; a
# headline and captions stacked under it read as two things shouting at once).
FULL_FRAME = {"statement", "flicker", "cta", "hook"}
WORD_GRAPHICS = {"two", "keyword", "list", "flow"}
# Never the big word of a caption line.
WEAK = {"a", "an", "the", "and", "but", "or", "so", "to", "of", "in", "on", "at", "it", "is", "was", "be", "we", "we've", "i",
        "i'm", "you", "your", "they", "he", "she", "this", "that", "with", "for", "do", "did", "not", "just", "very", "really",
        "um", "uh", "like", "have", "has", "had", "are", "were", "our", "my", "me", "up", "all", "any", "going", "as", "you're",
        "that's", "it's", "get", "got", "try", "think", "what", "will", "can", "would", "could", "should", "there", "here", "then",
        "than", "about", "into", "from", "by", "if", "when", "how", "kind", "lot", "thing", "things", "actually", "first", "ago"}


# ------------------------------------------------------------------ brief

HOOK_WORDS = (3, 9)


def hook_text(*options: str) -> str:
    """The first option that reads as a hook headline (a few words, not one topic word), tidied; else ""."""
    for text in options:
        text = " ".join((text or "").split())
        if HOOK_WORDS[0] <= len(text.split()) <= HOOK_WORDS[1]:
            return text[:70]
    return ""


def brief_of(d: DirectorPlan, audio: AudioReport, target: float, headline: str = "", taken: set[str] | None = None,
             footage_accent: str = "", seed: str = "") -> tuple[Brief, str]:
    """The path follows the measured audio; when the director disagrees, the safer reading wins and is noted. The
    type kit is the director's when its style allows it and no reel in ``taken`` (sibling reels, the creator's recent
    ones) has it; the kit chosen is added to ``taken``."""
    measured = audio.kind
    note = ""
    if (measured in VOICE_KINDS) != (d.audio_view in VOICE_KINDS):
        if measured in VOICE_KINDS and audio.lyrics:
            measured = "song"
        note = f"Listen measured {audio.kind}, the director heard {d.audio_view}; edited as {measured}."
    path = "voice" if measured in VOICE_KINDS else "visual"
    r = recipe(d.recipe)
    caption_mode = d.caption_mode if path == "voice" and not d.burned_captions else "none"
    music = d.music if d.music != "none" else r["music"]
    if path == "visual":
        music = "score"
    import random
    # Add variety - if director picked a style, maybe rotate or randomize sometimes
    style_name = d.style
    all_styles = styles.names()
    if not style_name or style_name not in all_styles:
        style_name = random.choice(all_styles)
    else:
        # 30% chance to pick a different style for more variety
        if random.random() < 0.3:
            style_name = random.choice([s for s in all_styles if s != style_name])
    style = styles.get(style_name)
    mood = styles.hold(style, d.mood)
    taken = taken if taken is not None else set()
    kit = typekits.choose(d.type_kit, style["name"], taken, seed or d.notes)
    taken.add(kit)
    mixed = typekits.mix(kit, d.mix_kits, style["name"], seed or d.notes)
    # The director's own type design for this reel when it keeps to the rules and no reel in ``taken`` has its look;
    # the catalogue kit otherwise.
    design = typekits.designed(d.text_style.model_dump()) or {}
    if design and typekits.signature(design) in taken:
        design = {}
    if design:
        taken.add(typekits.signature(design))
    accent = typekits.spec(kit, "text", footage_accent, kit=design or None)["vars"]["--accent"]
    brief = Brief(path=path, audio_kind=measured, recipe=r["id"], target_seconds=target or d.target_seconds,
                  type_kit=kit, mix_kits=mixed, kit=design, style=style["name"], caption_looks=style["caption_looks"],
                  title_lead=d.title_lead, title_text=d.title_text,
                  hook_word=(d.hooks[0].word if d.hooks else "").upper()[:12],
                  hook_text=hook_text(headline, d.hook_text) if path == "voice" else "",
                  caption_mode=caption_mode, music=music, mood=mood, accent=accent,
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


# Reframe rhythm: a long talking run is cut into sub-shots of about SUBSHOT seconds, alternating a tight punch-in with
# the wider frame, each cut in the gap between two words. The best human edits reframe every 1.5-2.5 s even inside one
# take; a 5 s static talking head is where viewers swipe.
SUBSHOT, SUBSHOT_MAX = 1.4, 2.2


def _subshots(words: list[Word], span: tuple[int, float, float, int, int]) -> list[tuple[float, float]]:
    """``span`` cut into about-SUBSHOT pieces at word gaps (never inside a word); a short span stays whole."""
    src, a, b, i0, i1 = span
    if b - a <= SUBSHOT_MAX:
        return [(a, b)]
    cuts, last = [], a
    for k in range(i0 + 1, i1 + 1):
        prev, word = words[k - 1], words[k]
        gap = (prev.t1 + word.t0) / 2
        if word.src == src and gap - last >= 0.7 and b - gap >= 0.7 and not word.filler:
            cuts.append(gap)
            last = gap
            if len(cuts) > 30:
                break
    edges = [a, *cuts, b]
    return list(zip(edges, edges[1:]))


def _beats(seconds: float, beat: float = BEAT) -> float:
    return max(0.5, round(seconds / beat * 2) / 2)


def _without(clips: list[DClip], hook: DClip) -> list[DClip]:
    """The story minus the hook's words: the line that opens the reel is not said a second time."""
    if hook.w0 < 0:
        return clips
    out = []
    for c in clips:
        if c.w0 < 0 or c.w1 < hook.w0 or c.w0 > hook.w1:
            out.append(c)
            continue
        if c.w0 < hook.w0:
            out.append(c.model_copy(update={"w1": hook.w0 - 1}))
        if c.w1 > hook.w1:
            out.append(c.model_copy(update={"w0": hook.w1 + 1}))
    return out


def video_track(d: DirectorPlan, brief: Brief, words: list[Word], shots: list[Shot], src_len: dict[int, float],
                hook_index: int = 0, beat: float = BEAT) -> list[VideoItem]:
    """The video track; picture clips are cut to whole half-beats of ``beat`` (the music's) from the start."""
    clips = list(d.story)
    if d.hooks:
        hook = d.hooks[min(hook_index, len(d.hooks) - 1)].clip
        clips = [hook.model_copy(update={"role": "hook", "zoom": "punch"})] + _without([c for c in clips if c.role != "hook"], hook)
    shot_seconds = recipe(brief.recipe)["shot_seconds"]
    items: list[VideoItem] = []
    import random
    seed = hash((brief.title_text or "", brief.notes or "")) % (2**32)
    rng = random.Random(seed)
    seen: set[tuple[int, int, int]] = set()
    for n, clip in enumerate(clips):
        section = clip.section if 0 <= clip.section < len(brief.sections) else -1
        if brief.path == "voice" and clip.w0 >= 0 and clip.w1 >= clip.w0 and words:
            k = 0
            for span in _talk_spans(words, clip.w0, clip.w1, src_len):
                src, sa, sb, i0, i1 = span
                for a, b in _subshots(words, span):
                    if b - a < 0.16:
                        continue
                    key = (src, int(round(a * 30)), int(round(b * 30)))
                    if key in seen:
                        continue
                    if k == 0:
                        zoom = clip.zoom if clip.zoom in ("in", "out", "punch", "hold") else rng.choice(["punch", "in", "out"])
                    elif clip.role == "hook":
                        zoom = "punch"
                    elif rng.random() < 0.28:
                        zoom = rng.choice(["punch", "in", "out"])
                    elif k % 5 == 1:
                        zoom = "in"
                    elif k % 5 == 3:
                        zoom = "out"
                    elif k % 5 == 0:
                        zoom = "punch"
                    else:
                        zoom = rng.choice(["in", "out", "punch", "hold"])
                    items.append(VideoItem(id=f"v{len(items)}", src=src, t0=round(a, 3), t1=round(b, 3), zoom=zoom, role=clip.role,
                                           section=section if k == 0 else -1, sound=clip.sound, money=clip.money, what=clip.what,
                                           keeps_voice=True))
                    seen.add(key)
                    k += 1
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
        s = start
        e = start + speed * out_len
        key = (clip.src, int(round(s * 30)), int(round(e * 30)))
        if key in seen:
            continue
        items.append(VideoItem(id=f"v{len(items)}", src=clip.src, t0=round(s, 3), t1=round(e, 3),
                               speed=round(speed, 4), zoom=clip.zoom, role=clip.role, section=section, sound=clip.sound,
                               money=clip.money, what=clip.what))
        seen.add(key)
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


def _same(a: str, b: str) -> bool:
    """Loose match of a spoken word to a label word: case, punctuation and endings ("students"/"student") aside."""
    a, b = a.lower().strip(".,!?'\""), b.lower().strip(".,!?'\"")
    return bool(a and b) and (a == b or (min(len(a), len(b)) >= 4 and a[:4] == b[:4]))


def _spoken_at(items: list[VideoItem], words: list[Word], w0: int, w1: int, labels: list[str]) -> list[float | None]:
    """Output second each label is said: its first strong word, searched in order from where the last one was found."""
    pool = words[max(0, w0 - 2):min(len(words), w1 + 12)]
    found: list[float | None] = []
    k = 0
    for label in labels:
        heads = [t for t in label.split() if t.lower().strip(".,!?") not in WEAK] or label.split()
        # The label's first word decides ("Average student" is not the "student" of the item before); later words
        # are a fallback for labels said in other words.
        hit = next((n for h in heads for n in range(k, len(pool)) if any(_same(p, h) for p in pool[n].text.split())), None)
        t = to_output(items, pool[hit].src, pool[hit].t0) if hit is not None else None
        if t is not None:
            k = hit + 1
        found.append(t)
    return found


def _steps(found: list[float | None], start: float, end: float) -> list[float]:
    """When each item lands, relative to the graphic: when it is said; items not heard sit between their neighbours."""
    n = len(found)
    known = [(k, t - start) for k, t in enumerate(found) if t is not None and t >= start - 0.1]
    if not known:
        gap = max(0.3, (end - start - 0.4) / max(1, n))
        return [round(0.2 + k * gap, 3) for k in range(n)]
    steps = []
    for k in range(n):
        before = [(i, v) for i, v in known if i <= k]
        after = [(i, v) for i, v in known if i >= k]
        if before and before[-1][0] == k:
            v = before[-1][1]
        elif before and after:
            (i0, v0), (i1, v1) = before[-1], after[0]
            v = v0 + (v1 - v0) * (k - i0) / (i1 - i0)
        elif before:
            v = before[-1][1] + 0.6 * (k - before[-1][0])
        else:
            v = max(0.05, after[0][1] - 0.6 * (after[0][0] - k))
        steps.append(round(max(0.05, v), 3))
    return [max(s, steps[i - 1] + 0.15) if i else s for i, s in enumerate(steps)]


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
    # A talking reel opens on its hook headline (the question it answers); a reel in chapters (three recipes, five tips)
    # opens on its title; a picture-only reel on one huge word.
    title_first = bool(hook and brief.title_text and len(brief.sections) >= 2 and not brief.hook_text)
    if hook and brief.hook_text:
        add("hook", hook.out0 + 0.05, min(max(hook.out1, hook.out0 + 2.2), hook.out0 + HOOK_SECONDS), {"text": brief.hook_text},
            place="top", why="hook word", by="finish")
    elif hook and title_first:
        add("two", hook.out0 + 0.15, min(hook.out1 + 0.4, hook.out0 + 2.6), {"lead": brief.title_lead, "text": brief.title_text},
            why="hook word", by="finish")
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
        elif k in ("list", "flow"):
            items_ = [i for i in beat.items if i][:5]
            if items_:
                # The panel opens as the first item is said and stays a beat past the last one; items land as spoken.
                found = _spoken_at(items, words, beat.w0, beat.w1, items_)
                heard = [t for t in found if t is not None]
                if heard:
                    start = max(0.0, heard[0] - 0.25)
                    end = max(end, heard[-1] + 1.2)
                end = max(end, start + 0.6 * len(items_) + 0.8)
                data = {"title": beat.lead, "items": items_, "mark": beat.mark} if k == "list" else {"items": items_}
                add(k, start, end, data, place="panel", why=beat.why, steps=_steps(found, start, end))
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
        elif k == "name":
            add("name", start, end, {"text": beat.text, "label": beat.lead}, why=beat.why)
    payoff = next((i for i in items if i.role == "payoff"), None) or (items[-2] if len(items) > 2 else None)
    if payoff and brief.title_text and not title_first:
        add("two", payoff.out0 + 0.1, min(payoff.out1, payoff.out0 + 2.6), {"lead": brief.title_lead, "text": brief.title_text},
            why="title over the payoff", by="finish")
    if items and brief.cta:
        last = items[-1]
        add("cta", max(last.out0, last.out1 - 2.2), last.out1 - 0.05, {"verb": brief.cta.upper(), "text": ""}, why="call to action", by="finish")
    out = _space(out)
    if brief.path == "voice":
        out = _few_cards(out, total)
    return out


def design_track(d: DirectorPlan, words: list[Word], items: list[VideoItem]) -> list[GraphicItem]:
    """The director's designed moments (motion_code.py) as timed graphics, not yet drawn. Each ends at the cut out of
    its shot when that still leaves it ``MIN_DESIGN`` seconds: a card held over the next shot reads as a leftover."""
    out: list[GraphicItem] = []
    for design in d.designs[:MAX_DESIGNS]:
        span = _word_times(items, words, design.w0, design.w1)
        if span is None:
            continue
        start, end = span
        item = next((i for i in items if i.out0 <= start < i.out1), None)
        end = min(end + DESIGN_TAIL, item.out1 if item and item.out1 - start >= MIN_DESIGN else end + DESIGN_TAIL)
        if end - start < MIN_DESIGN:
            continue
        said = [w for w in words[design.w0:design.w1 + 1] if not w.filler]
        line = [{"text": w.text, "at": round(t - start, 2)} for w in said
                for t in [to_output(items, w.src, w.t0)] if t is not None]
        out.append(GraphicItem(id=f"d{len(out)}", kind="code", start=round(start, 3), end=round(end, 3), box=[0, 0, 1080, 1920],
                               data={"line": " ".join(w["text"] for w in line), "words": line}, place="free",
                               why=design.why, by="design"))
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

# Words that lean on the next one: a caption line never ends on them ("the | car", "ko | balance kar", "oka | roju").
BINDING = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with", "and", "or", "but", "so", "that", "this", "my", "your",
           "our", "their", "his", "her", "its", "is", "are", "was", "were", "be", "i", "you", "we", "they", "he", "she", "as", "if",
           "than", "very", "really", "just", "from", "into", "about", "not", "no", "can", "will", "would", "should", "could",
           # Hindi and Telugu: linking words and verb stems lean forward; postpositions (ko, se, mein, lo, ni) close a phrase.
           "ka", "ke", "aur", "ya", "jo", "ek", "koi", "kya", "kaise", "ye", "yeh", "wo", "woh", "us", "itni", "itna", "kitna",
           "bahut", "kar", "karke", "oka", "mariyu", "ee", "aa", "chala"}
MAX_LINE_WORDS, MAX_LINE_CHARS = 6, 30


def phrase_lines(kept: list[tuple[Word, float, float]]) -> list[list[tuple[Word, float, float]]]:
    """Caption lines that follow the speech's phrasing: broken at pauses and punctuation, 2-6 words, never ending on a
    word that leans on the next one, never running over a long pause. Chosen as a whole (dynamic programming)."""
    n = len(kept)
    if n == 0:
        return []

    def pause_after(i: int) -> float:
        return kept[i + 1][1] - kept[i][2] if i + 1 < n else 9.0

    def cost(i: int, j: int) -> float:  # one line of kept[i:j]
        size = j - i
        text = " ".join(e[0].text for e in kept[i:j])
        last = kept[j - 1][0].text.strip().lower()
        c = 0.5 * (size - 4) ** 2 + max(0, len(text) - MAX_LINE_CHARS) * 0.3
        c += sum(4.0 for k in range(i, j - 1) if pause_after(k) > 0.6)  # a long pause inside a line
        c += sum(2.0 for k in range(i, j - 1)  # a sentence end, or a clear breath, inside a line
                 if kept[k][0].text.strip().endswith((".", "?", "!")) or 0.35 <= pause_after(k) <= 0.6)
        if j < n:
            ends_phrase = last.endswith((".", "?", "!", ",", ";", ":")) or pause_after(j - 1) >= 0.35
            c += 0.0 if ends_phrase else (2.5 if last.strip(".,!?") in BINDING else 0.8)
        return c

    best = [0.0] + [float("inf")] * n
    back = [0] * (n + 1)
    for j in range(1, n + 1):
        for size in range(1, min(MAX_LINE_WORDS, j) + 1):
            i = j - size
            extra = 3.0 if size == 1 and n > 1 else 0.0  # a lone word is a last resort
            total = best[i] + cost(i, j) + extra
            if total < best[j]:
                best[j], back[j] = total, i
    lines, j = [], n
    while j > 0:
        lines.append(kept[back[j]:j])
        j = back[j]
    return lines[::-1]


def _spoken(text: str) -> set[str]:
    return {t for t in (w.lower().strip(".,!?'\"") for w in text.split()) if t and t not in WEAK}


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
                kept.append((w, round(item.out0 + (w.t0 - item.t0) / item.speed, 3), round(item.out0 + (min(w.t1, item.t1) - item.t0) / item.speed, 3)))
    # A stutter ("and and") shows once.
    kept = [e for k, e in enumerate(kept) if k == 0 or e[0].text.lower().strip(",.") != kept[k - 1][0].text.lower().strip(",.")]
    lines = phrase_lines(kept)
    def blocking() -> list[tuple[float, float, set[str] | None]]:
        """(start, end, words it shows) of each graphic a caption gives way to; None hides every word."""
        hiding = [(g.start, g.end, None) for g in graphics if g.kind == "effect" and g.data.get("captions") == "hide"]
        if brief.caption_mode == "every_word":
            return hiding + [(g.start, g.end, None if g.kind in FULL_FRAME else _spoken(" ".join(
                        [str(g.data.get(k, "")) for k in ("lead", "text", "title")] + [str(i) for i in g.data.get("items", [])])))
                    for g in graphics if g.kind in FULL_FRAME | WORD_GRAPHICS]
        return hiding + [(g.start, g.end, None) for g in graphics if g.kind in CARD_KINDS or g.place == "card" or g.kind in CAPTION_YIELDS_TO]

    cards = blocking()
    tags = [g for g in graphics if g.kind == "tag"]
    out: list[CaptionLine] = []
    used_tags: set[str] = set()
    runs: list[tuple[list[tuple[Word, float, float]], float]] = []
    for n, line in enumerate(lines):
        next_start = lines[n + 1][0][1] if n + 1 < len(lines) else float("inf")
        if d.drop_word in {w.i for w, _, _ in line}:
            # The payoff line is the reel's big moment: a card still up when it starts ends there.
            for g in graphics:
                if (g.kind in CARD_KINDS or g.place == "card") and g.start < line[0][1] < g.end:
                    g.end = round(max(g.start + 0.6, line[0][1] - 0.05), 3)
            cards = blocking()
        # Only the words said while a graphic holds the screen are hidden; the rest of the line shows around it.
        run: list[tuple[Word, float, float]] = []
        for entry in line + [None]:
            covered = entry is not None and any((a <= entry[1] < b or (a < entry[2] and entry[1] < b))
                                                and (shown is None or _spoken(entry[0].text) & shown) for a, b, shown in cards)
            if entry is not None and not covered:
                run.append(entry)
                continue
            if run and (len(run) >= MIN_LINE_WORDS - 1 or len(run) == len(line)):
                after = min([a for a, _, shown in cards if shown is None and a > run[0][1]] + [next_start])
                runs.append((run, min(run[-1][2] + 0.5, after)))
            run = []
    for line, end in runs:
        start = line[0][1]
        ids = {w.i for w, _, _ in line}
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
        elif key and len(out) % EMOJI_EVERY == 1:
            # Every few lines the big word may earn an animated emoji; the icon check drops it unless one truly fits.
            icon_query = key.text
        payoff = d.drop_word in ids
        out.append(CaptionLine(id=f"c{len(out)}", start=round(start, 3), end=round(end, 3), lead=lead, keyword=key.text if key else "",
                               words=spoken, icon_query=icon_query, payoff=payoff))
    graphics = [g for g in graphics if g.id not in used_tags]
    return out, graphics
