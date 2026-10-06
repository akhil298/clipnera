"""Motion graphics drawn as an ASS script, burned with the captions.

Every template shares one look: white cards with a soft shadow, the accent for
headers and ticks, Montserrat ExtraBold for words and Anton for big figures,
and one way of moving: slide up and fade in, fade out. Positions come from the
layout the cut has at that moment, so a card sits on the speaker's chest, in
the audience cell under shown content, or over gameplay, and never on a face,
on the content itself, or on the title card in the opening seconds.

Times here are seconds of the rendered file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from subtitle_styling.ass_generator import (
    ass_font_size,
    ass_time,
    escape_ass,
    face_metrics,
    rounded_rect,
    text_width,
)
from subtitle_styling.emoji_art import colourize

from motion.plan import BIG_NUMBER, CTA_CARD, ENTITY_TAG, LIST_CARD, REACTION

WORD_FAMILY, WORD_FILE = "Montserrat ExtraBold", "Montserrat-ExtraBold.ttf"
FIGURE_FAMILY, FIGURE_FILE = "Anton", "Anton-Regular.ttf"
# ASS colours are &HAABBGGRR.
WHITE = "&H00FFFFFF&"
INK = "&H00141414&"
ACCENT = "&H0020B0FF&"  # #FFB020
SOFT_INK = "&H00505050&"
SHADOW_ALPHA = "&H70&"
# Seconds for the shared entrance (slide up and fade) and exit (fade).
ENTER_MS, EXIT_MS = 220, 180
SLIDE_PX = 40
# Nothing may sit above this share of the height while the title card is up,
# nor below the platform's caption-and-buttons zone.
TITLE_BOTTOM = 0.17
SAFE_TOP, SAFE_BOTTOM = 0.10, 0.82
CARD_WIDTH = 0.82
# Over shown content the title card moves off it: just under the seam's captions,
# this share of the height below the seam, taking about this much room.
TITLE_BELOW_SEAM = 0.04
TITLE_BAND = 0.1
# Scales a list card tries, largest first; the smallest keeps items near caption size.
LIST_CARD_SIZES = (1.0, 0.85, 0.7)
# Space kept clear around a face, as a share of its size.
FACE_MARGIN = 0.2


@dataclass(frozen=True)
class LayoutSpan:
    """The cut's layout from ``start`` to ``end``: its kind, its top cell's share
    of the height, and the faces on screen as normalised ``(x, y, w, h)``."""

    start: float
    end: float
    kind: str
    top: float = 0.0
    faces: tuple[tuple[float, float, float, float], ...] = ()

    @classmethod
    def from_stored(cls, item: dict) -> "LayoutSpan":
        return cls(float(item["start"]), float(item["end"]), str(item["kind"]), float(item.get("top") or 0.0),
                   tuple(tuple(float(v) for v in face) for face in item.get("faces") or []))


@dataclass
class Placed:
    """A cue on the rendered file's timeline."""

    kind: str
    start: float
    end: float
    data: dict
    beats: list[float] = field(default_factory=list)


def graphics_ass(
    cues: list[Placed], layouts: list[LayoutSpan], width: int, height: int, title_until: float,
    drawn: list[Placed] | None = None,
) -> str | None:
    """The ASS script drawing ``cues``, or ``None`` when none of them fits.

    Cues that found a place are appended to ``drawn``: only those get sounds,
    and only those move the captions aside.
    """
    events: list[str] = []
    for cue in cues:
        layout = _layout_at(layouts, cue.start)
        lines = _DRAW[cue.kind](cue, layout, width, height, cue.start < title_until)
        if lines:
            events.extend(lines)
            if drawn is not None:
                drawn.append(cue)
    if not events:
        return None
    header = [
        "[Script Info]", "Title: Clipnera motion graphics", "ScriptType: v4.00+",
        f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: MGWord,{WORD_FAMILY},40,&H00141414,&H00141414,&H00141414,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: MGFigure,{FIGURE_FAMILY},40,&H00FFFFFF,&H00FFFFFF,&H00141414,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1",
        "Style: MGShape,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return colourize("\n".join(header + events) + "\n")


def _layout_at(layouts: list[LayoutSpan], t: float) -> LayoutSpan:
    return next((span for span in layouts if span.start <= t < span.end), LayoutSpan(0.0, 0.0, "follow"))


def title_position(layout: LayoutSpan) -> float | None:
    """Where the title card's top goes (share of the height) when the clip opens
    on ``layout``; ``None`` keeps the style's own place. Over shown content
    the title would cover it, so it moves under the seam's captions."""
    return layout.top + TITLE_BELOW_SEAM if layout.kind == "screen_with_speaker" else None


def _below_title(layout: LayoutSpan) -> float:
    """The highest a graphic may start while the title card is up, as a share of the height."""
    moved = title_position(layout)
    return moved + TITLE_BAND if moved is not None else TITLE_BOTTOM


def card_centre(layout: LayoutSpan) -> float:
    """Where a card's centre goes, as a share of the height, for the layout under it."""
    if layout.kind == "screen_with_speaker":
        return layout.top + (1 - layout.top) * 0.62  # chests of the audience, under the content
    if layout.kind == "two_speaker_stack":
        return layout.top * 0.74  # the upper speaker's chest, clear of the seam captions
    if layout.kind == "split_gameplay":
        return layout.top + (1 - layout.top) * 0.5  # over the gameplay, below the facecam
    if layout.kind == "content":
        return 0.8  # under the content, on its blurred backdrop
    return 0.64  # one speaker: below the face, above the captions' usual line


def _band(layout: LayoutSpan, height: int, box_h: float, under_title: bool,
          left: float = 0.0, right: float = 1.0) -> float | None:
    """Top edge for a box ``box_h`` tall spanning ``left``..``right`` of the width.

    It goes as near the layout's spot for cards as it can while staying on
    screen, off the shown content, and clear of every face; ``None`` when no
    such place exists, and the graphic is then left out.
    """
    lowest = SAFE_BOTTOM * height - box_h
    highest = max(SAFE_TOP, _below_title(layout) if under_title else 0.0) * height
    if layout.kind == "screen_with_speaker":
        highest = max(highest, layout.top * height + 12)  # never over the shown content
    if lowest < highest:
        return None
    preferred = min(max(card_centre(layout) * height - box_h / 2, highest), lowest)
    step = height * 0.01
    offsets = sorted({round(k * step, 3) for k in range(-100, 101)}, key=abs)
    for offset in offsets:
        top = preferred + offset
        if highest <= top <= lowest and not _covers_face(layout, left, top / height, right, (top + box_h) / height):
            return top
    return None


def _covers_face(layout: LayoutSpan, left: float, top: float, right: float, bottom: float) -> bool:
    """Whether the box overlaps a face, with a margin of a fifth of the face around it."""
    for x, y, w, h in layout.faces:
        mx, my = w * FACE_MARGIN, h * FACE_MARGIN
        if left < x + w + mx and x - mx < right and top < y + h + my and y - my < bottom:
            return True
    return False


def _timing(start: float, end: float) -> str:
    return f"{ass_time(start)},{ass_time(end)}"


def _enter(x: float, y: float) -> str:
    """Slide up into ``(x, y)`` and fade in; fade out at the end."""
    return f"\\move({x:.0f},{y + SLIDE_PX:.0f},{x:.0f},{y:.0f},0,{ENTER_MS})\\fad({ENTER_MS},{EXIT_MS})"


def _shape(start: float, end: float, x: float, y: float, drawing: str, colour: str, layer: int,
           extra: str = "") -> str:
    return (
        f"Dialogue: {layer},{_timing(start, end)},MGShape,,0,0,0,,"
        f"{{\\an7{_enter(x, y)}\\bord0\\shad0\\1c{colour}{extra}\\p1}}{drawing}{{\\p0}}"
    )


def _card(start: float, end: float, left: float, top: float, w: float, h: float, r: float, s: float) -> list[str]:
    """A white card with a soft shadow under it."""
    return [
        _shape(start, end, left, top + 10 * s, rounded_rect(w, h, r), INK, 0, f"\\1a{SHADOW_ALPHA}\\blur{14 * s:.0f}"),
        _shape(start, end, left, top, rounded_rect(w, h, r), WHITE, 1),
    ]


def _text(start: float, end: float, x: float, y: float, text: str, size: int, colour: str, layer: int,
          align: int = 7, extra: str = "", style: str = "MGWord") -> str:
    return (
        f"Dialogue: {layer},{_timing(start, end)},{style},,0,0,0,,"
        f"{{\\an{align}{_enter(x, y)}\\fs{size}\\bord0\\shad0\\1c{colour}{extra}}}{text}"
    )


def _list_card(cue: Placed, layout: LayoutSpan, width: int, height: int, under_title: bool) -> list[str]:
    s = width / 1080
    items = cue.data.get("items") or []
    if not items or len(cue.beats) != len(items):
        return []
    # The largest size that fits clear of every face; a list matters enough
    # to be drawn smaller rather than not at all, down to a readable floor.
    for factor in LIST_CARD_SIZES:
        em = 56 * s * factor
        title_em = 50 * s * factor
        pad = 36 * s * factor
        row = em * 1.55
        header = title_em * 1.75
        card_w = width * CARD_WIDTH * (0.5 + 0.5 * factor)
        card_h = pad + header + 18 * s * factor + row * len(items) + pad * 0.6
        left = (width - card_w) / 2
        top = _band(layout, height, card_h, under_title, left / width, (left + card_w) / width)
        if top is not None:
            break
    else:
        return []
    descent, cap = face_metrics(WORD_FILE)
    box = em * 0.9
    text_left = left + pad + box + 22 * s
    room = card_w - (text_left - left) - pad - em * 1.2
    if any(text_width(item["text"], WORD_FILE, em, em) > room for item in items):
        return []
    start, end = cue.start, cue.end
    events = _card(start, end, left, top, card_w, card_h, 30 * s, s)
    # Header: an accent bar across the top of the card with the title on it.
    events.append(_shape(start, end, left + pad * 0.6, top + pad * 0.6, rounded_rect(card_w - pad * 1.2, header, 18 * s),
                         ACCENT, 2))
    events.append(_text(start, end, width / 2, top + pad * 0.6 + header / 2, escape_ass(cue.data.get("title", "")).upper(),
                        ass_font_size(title_em, WORD_FAMILY), INK, 3, align=5))
    size = ass_font_size(em, WORD_FAMILY)
    for index, (item, beat) in enumerate(zip(items, cue.beats)):
        row_top = top + pad + header + 18 * s * factor + index * row
        box_top = row_top + (row - box) / 2
        events.append(_shape(start, end, left + pad, box_top, rounded_rect(box, box, 8 * s), SOFT_INK, 2))
        events.append(_shape(start, end, left + pad + 4 * s, box_top + 4 * s,
                             rounded_rect(box - 8 * s, box - 8 * s, 6 * s), WHITE, 3))
        at = max(start, beat)
        # The tick pops into the box as the item is said.
        tick = _tick(box * 0.8)
        events.append(
            f"Dialogue: 4,{_timing(at, end)},MGShape,,0,0,0,,"
            f"{{\\an5\\pos({left + pad + box / 2:.0f},{box_top + box / 2:.0f})\\fad(60,{EXIT_MS})\\bord0\\shad0"
            f"\\1c{ACCENT}\\fscx40\\fscy40\\t(0,120,\\fscx120\\fscy120)\\t(120,200,\\fscx100\\fscy100)\\p1}}{tick}{{\\p0}}"
        )
        # The words type on, left to right, over the time they are said.
        sweep = max(20, min(60, round((cue.beats[index + 1] - beat) * 100 * 0.5) if index + 1 < len(items) else 45))
        baseline_bottom = row_top + row / 2 + (cap / 2 + descent) * em
        icon = f" {item['icon']}" if item.get("icon") else ""
        events.append(
            f"Dialogue: 4,{_timing(at, end)},MGWord,,0,0,0,,"
            f"{{\\an1\\pos({text_left:.0f},{baseline_bottom:.0f})\\fad(0,{EXIT_MS})\\fs{size}\\bord0\\shad0"
            f"\\1c{INK}\\2a&HFF&\\kf{sweep}}}{escape_ass(item['text'])}{icon}"
        )
    return events


def _tick(size: float) -> str:
    """A check mark drawn in a ``size`` square, from its top-left."""
    w = size
    return (
        f"m {0.05 * w:.1f} {0.55 * w:.1f} l {0.38 * w:.1f} {0.88 * w:.1f} l {0.95 * w:.1f} {0.18 * w:.1f} "
        f"l {0.82 * w:.1f} {0.05 * w:.1f} l {0.38 * w:.1f} {0.62 * w:.1f} l {0.18 * w:.1f} {0.42 * w:.1f}"
    )


_FIGURE = re.compile(r"^(?P<prefix>[^\d]*)(?P<number>\d[\d,]*(?:\.\d+)?)(?P<suffix>.*)$")
COUNT_STEPS = 12
COUNT_SECONDS = 0.5


def count_up(value: str) -> list[str]:
    """The texts a figure counts through on its way to ``value`` ("$10,000"), ending on it."""
    match = _FIGURE.match(value.strip())
    if not match:
        return [value]
    raw = match.group("number")
    target = float(raw.replace(",", ""))
    if target < 10:
        return [value]
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    texts = []
    for step in range(1, COUNT_STEPS + 1):
        current = target * (1 - (1 - step / COUNT_STEPS) ** 3)  # eases out, slowing into the value
        shown = f"{current:,.{decimals}f}" if "," in raw else f"{current:.{decimals}f}"
        texts.append(f"{match.group('prefix')}{shown}{match.group('suffix')}")
    texts[-1] = value
    return texts


def _big_number(cue: Placed, layout: LayoutSpan, width: int, height: int, under_title: bool) -> list[str]:
    s = width / 1080
    value = cue.data.get("value", "")
    label = cue.data.get("label", "")
    em = 210 * s
    while text_width(value, FIGURE_FILE, em, em) > width * 0.86 and em > 110 * s:
        em *= 0.92
    if text_width(value, FIGURE_FILE, em, em) > width * 0.86:
        return []
    label_em = 50 * s
    box_h = em * 1.15 + (label_em * 1.9 if label else 0)
    span = max(text_width(value, FIGURE_FILE, em, em), text_width(label.upper(), WORD_FILE, label_em, label_em)) / width
    top = _band(layout, height, box_h, under_title, 0.5 - span / 2 - 0.03, 0.5 + span / 2 + 0.03)
    if top is None:
        return []
    cx, cy = width / 2, top + em * 0.58
    size = ass_font_size(em, FIGURE_FAMILY)
    look = f"\\fs{size}\\bord{10 * s:.0f}\\3c{INK}\\shad{6 * s:.0f}\\4c{ACCENT}\\4a&H00&"
    events: list[str] = []
    steps = count_up(value)
    step_seconds = COUNT_SECONDS / len(steps)
    for index, text in enumerate(steps):
        last = index == len(steps) - 1
        at = cue.start + index * step_seconds
        until = cue.end if last else at + step_seconds
        motion = (f"\\fscx112\\fscy112\\t(0,160,\\fscx100\\fscy100)\\fad(0,{EXIT_MS})" if last
                  else ("\\fad(120,0)" if index == 0 else ""))
        events.append(
            f"Dialogue: 5,{_timing(at, until)},MGFigure,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{cy:.0f}){look}{motion}}}{escape_ass(text)}"
        )
    if label:
        label_size = ass_font_size(label_em, WORD_FAMILY)
        label_w = text_width(label.upper(), WORD_FILE, label_em, label_em) + 44 * s
        pill_h = label_em * 1.55
        pill_top = top + em * 1.18
        events.append(_shape(cue.start, cue.end, cx - label_w / 2, pill_top, rounded_rect(label_w, pill_h, pill_h / 2),
                             WHITE, 4))
        events.append(_text(cue.start, cue.end, cx, pill_top + pill_h / 2, escape_ass(label).upper(), label_size, INK, 5,
                            align=5))
    return events


def _entity_tag(cue: Placed, layout: LayoutSpan, width: int, height: int, under_title: bool) -> list[str]:
    s = width / 1080
    text = cue.data.get("text", "")
    icon = cue.data.get("icon", "")
    em = 54 * s
    label = f"{icon} {escape_ass(text)}".strip()
    pill_w = text_width(label, WORD_FILE, em, em) + 56 * s
    pill_h = em * 1.7
    if pill_w > width * 0.8:
        return []
    x = 56 * s
    y = max(SAFE_TOP, _below_title(layout) + 0.04 if under_title else 0.16) * height
    if layout.kind == "screen_with_speaker":
        # Top-left of the audience cell, under the content (and the title while it is up).
        y = (_below_title(layout) if under_title else layout.top) * height + 28 * s
    if _covers_face(layout, x / width, y / height, (x + pill_w) / width, (y + pill_h) / height):
        return []
    start, end = cue.start, cue.end
    return [
        _shape(start, end, x, y + 8 * s, rounded_rect(pill_w, pill_h, pill_h / 2), INK, 0,
               f"\\1a{SHADOW_ALPHA}\\blur{10 * s:.0f}"),
        _shape(start, end, x, y, rounded_rect(pill_w, pill_h, pill_h / 2), ACCENT, 1),
        _text(start, end, x + pill_w / 2, y + pill_h / 2, label, ass_font_size(em, WORD_FAMILY), INK, 2, align=5),
    ]


def _cta_card(cue: Placed, layout: LayoutSpan, width: int, height: int, under_title: bool) -> list[str]:
    s = width / 1080
    label = cue.data.get("label", "")
    value = cue.data.get("value", "")
    label_em = 58 * s
    value_em = 160 * s
    while value and text_width(value, WORD_FILE, value_em, value_em) > width * 0.86 and value_em > 80 * s:
        value_em *= 0.92
    if value and text_width(value, WORD_FILE, value_em, value_em) > width * 0.86:
        return []
    box_h = label_em * 1.4 + (value_em * 1.2 if value else 0)
    span = max(text_width(value, WORD_FILE, value_em, value_em) if value else 0,
               text_width(label, WORD_FILE, label_em, label_em)) / width
    top = _band(layout, height, box_h, under_title, 0.5 - span / 2 - 0.03, 0.5 + span / 2 + 0.03)
    if top is None:
        return []
    cx = width / 2
    pop = "\\fscx70\\fscy70\\t(0,140,\\fscx106\\fscy106)\\t(140,240,\\fscx100\\fscy100)"
    events = [
        f"Dialogue: 5,{_timing(cue.start, cue.end)},MGWord,,0,0,0,,"
        f"{{\\an5\\pos({cx:.0f},{top + label_em * 0.7:.0f})\\fad(120,{EXIT_MS})\\fs{ass_font_size(label_em, WORD_FAMILY)}"
        f"\\1c{ACCENT}\\bord{7 * s:.0f}\\3c{INK}\\shad0{pop}}}{escape_ass(label)}",
    ]
    if value:
        y = top + label_em * 1.4 + value_em * 0.6
        size = ass_font_size(value_em, WORD_FAMILY)
        events += [
            # A soft accent glow behind the code, then the crisp code over it.
            f"Dialogue: 5,{_timing(cue.start, cue.end)},MGWord,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{y:.0f})\\fad(120,{EXIT_MS})\\fs{size}\\1c{WHITE}\\bord{16 * s:.0f}\\3c{ACCENT}"
            f"\\3a&H60&\\blur{14 * s:.0f}\\shad0{pop}}}{escape_ass(value)}",
            f"Dialogue: 6,{_timing(cue.start, cue.end)},MGWord,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{y:.0f})\\fad(120,{EXIT_MS})\\fs{size}\\1c{WHITE}\\bord{5 * s:.0f}\\3c{INK}"
            f"\\shad0{pop}}}{escape_ass(value)}",
        ]
    return events


def _reaction(cue: Placed, layout: LayoutSpan, width: int, height: int, under_title: bool) -> list[str]:
    s = width / 1080
    emoji = cue.data.get("emoji", "")
    if not emoji:
        return []
    size = round(220 * s)
    half = size * 0.6 / width
    x = width * 0.8
    y = (layout.top + (1 - layout.top) * 0.2) * height if layout.kind in ("screen_with_speaker", "two_speaker_stack") \
        else 0.4 * height
    y = max(y, (_below_title(layout) if under_title else SAFE_TOP) * height + size)
    for side in (0.8, 0.2):  # beside the face, on whichever side is free
        x = width * side
        if not _covers_face(layout, side - half, (y - size * 0.6) / height, side + half, (y + size * 0.6) / height):
            break
    else:
        return []
    return [
        f"Dialogue: 6,{_timing(cue.start, cue.end)},MGWord,,0,0,0,,"
        f"{{\\an5\\pos({x:.0f},{y:.0f})\\fad(60,{EXIT_MS})\\fs{size}\\bord0\\shad0"
        f"\\fscx30\\fscy30\\frz-14\\t(0,150,\\fscx125\\fscy125\\frz8)\\t(150,280,\\fscx100\\fscy100\\frz0)}}{emoji}"
    ]


_DRAW = {
    LIST_CARD: _list_card,
    BIG_NUMBER: _big_number,
    ENTITY_TAG: _entity_tag,
    CTA_CARD: _cta_card,
    REACTION: _reaction,
}
