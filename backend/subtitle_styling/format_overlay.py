"""On-screen overlays for list formats: a counter for listicles, a board for rankings.

The director labels each item of a listicle or ranking (``format_items``, in
source seconds). :func:`place_format_items` lays them on the rendered clip's
timeline once, for both the burner and the editor preview: after the hook
teaser, with the pauses the edit cut out removed. :func:`overlay_events` then
draws them as ASS events in a band of the frame that the title card, the
captions and any stacked seam leave free.
"""

from __future__ import annotations

from typing import Any

from clip_generation.hook import Hook, Span, body_duration, on_output_timeline
from formats.taxonomy import recipe_for
from subtitle_styling.ass_generator import (
    TITLE_FAMILY,
    TITLE_FONT_FILE,
    _contrast_on,
    ass_font_size,
    ass_time,
    escape_ass,
    rounded_rect,
    script_font,
    text_width,
    wrap_title,
)
from subtitle_styling.emoji_art import EMOJI

# Fewer than this many items is not a list worth counting.
MIN_ITEMS = 2
# An item on screen for less than this cannot be read.
MIN_ITEM_SECONDS = 1.5
MAX_LABEL_CHARS = 48
# A ranking's board shows at most this many slots ("top 10").
MAX_RANK_SLOTS = 10
OVERLAY_STYLE = "FormatOverlay"
# Sizes on a 1080px short side, like the caption templates.
COUNTER_EM, LABEL_EM, BOARD_ROW_PX = 60.0, 44.0, 64.0
LABEL_MAX_WIDTH = 0.82
BOARD_WIDTH = 0.46
# Kept clear of the frame's top and bottom edges, as shares of its height.
SAFE_TOP, SAFE_BOTTOM = 0.04, 0.94
# Space kept between the overlay and anything it must not touch, in px at 1080.
CLEARANCE = 24.0
PANEL = "\\1c&H000000&\\1a&H60&"
WHITE, BLACK = "&H00FFFFFF", "&H00000000"
FADE = "\\fad(120,150)"


def overlay_kind(content_format: str | None) -> str:
    """The overlay a clip of ``content_format`` gets: ``none``, ``list_counter`` or ``rank_board``."""
    return recipe_for(content_format).overlay


def place_format_items(
    items: list[dict[str, Any]] | None,
    content_format: str | None,
    clip_start: float,
    clip_end: float,
    hook: Hook | None = None,
    spans: list[Span] | None = None,
    gap: float = 0.0,
) -> list[dict[str, Any]]:
    """The clip's list items on the rendered file's timeline, ready to draw.

    Each is ``{start, end, label, number, rank}``: ``start``/``end`` in seconds
    of the output (teaser and any ``gap`` of bridge first), ``end`` held until
    the next item appears, ``number`` the item's place in the order spoken, and
    ``rank`` its rank on a ranking's board (``None`` on a listicle). Empty
    unless the format has an overlay and at least ``MIN_ITEMS`` items play.
    """
    kind = overlay_kind(content_format)
    if kind == "none" or not items:
        return []
    body = body_duration(clip_start, clip_end, spans)
    offset = (hook.duration if hook else 0.0) + gap
    placed: list[dict[str, Any]] = []
    for item in items:
        label = _label(item)
        timing = _body_timing(item, clip_start, clip_end, spans, body)
        if label and timing:
            placed.append({"start": offset + timing[0], "end": offset + timing[1], "label": label,
                           "rank": _int(item.get("rank"))})
    if len(placed) < MIN_ITEMS:
        return []

    placed.sort(key=lambda p: p["start"])
    for number, (item, following) in enumerate(zip(placed, [*placed[1:], None]), start=1):
        item["number"] = number
        until = following["start"] if following else max(item["end"], item["start"] + MIN_ITEM_SECONDS)
        item["end"] = round(min(until, offset + body), 3)
        item["start"] = round(item["start"], 3)
    if kind == "rank_board":
        _assign_ranks(placed)
    else:
        for item in placed:
            item["rank"] = None
    return placed


def overlay_events(
    kind: str,
    items: list[dict[str, Any]],
    width: int,
    height: int,
    duration: float,
    accent: str,
    occupied: list[tuple[float, float]],
) -> tuple[list[str], list[str]]:
    """``(style lines, dialogue lines)`` drawing ``items`` (from :func:`place_format_items`).

    ``accent`` is an ASS colour; ``occupied`` are vertical pixel ranges the
    title card, captions and seams use, which the overlay keeps clear of.
    """
    if kind == "none" or len(items) < MIN_ITEMS:
        return [], []
    family, font_file = script_font(" ".join(i["label"] for i in items)) or (TITLE_FAMILY, TITLE_FONT_FILE)
    scale = min(width, height) / 1080.0
    # One style for every overlay event; each sets its own size and colours.
    style = (
        f"Style: {OVERLAY_STYLE},{family},{ass_font_size(LABEL_EM * scale, family)},"
        f"{WHITE},{WHITE},{BLACK},{BLACK},-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1"
    )
    draw = _Draw(family, font_file, scale, accent, duration)
    if kind == "rank_board":
        slots = max(item["rank"] for item in items)
        band = _band(occupied, height, scale, min(slots, 5) * BOARD_ROW_PX * scale)
        return [style], draw.rank_board(items, width, band, slots)
    band = _band(occupied, height, scale, (COUNTER_EM * 1.56 + LABEL_EM * 2.8) * scale)
    return [style], draw.list_counter(items, width, band)


class _Draw:
    def __init__(self, family: str, font_file: str, scale: float, accent: str, duration: float) -> None:
        self.family, self.font_file, self.scale = family, font_file, scale
        self.accent, self.ink, self.duration = accent, _contrast_on(accent), duration

    def list_counter(self, items: list[dict[str, Any]], width: int, band: tuple[float, float]) -> list[str]:
        """A "3/5" badge with the item's label under it, at the top of ``band``, during each item."""
        counter_em, label_em = COUNTER_EM * self.scale, LABEL_EM * self.scale
        pad_x, pad_y = 0.55 * counter_em, 0.28 * counter_em
        badge_h = counter_em + 2 * pad_y
        centre_x = round(width / 2)
        badge_y = band[0] + badge_h / 2
        label_top = band[0] + badge_h + 0.3 * label_em
        events: list[str] = []
        for item in items:
            text = f"{item['number']}/{len(items)}"
            badge_w = text_width(text, self.font_file, counter_em, 0) + 2 * pad_x
            timing = f"{ass_time(item['start'])},{ass_time(item['end'])}"
            pop = f"\\fscx70\\fscy70\\t(0,160,\\fscx100\\fscy100){FADE}"
            events.append(
                f"Dialogue: 3,{timing},{OVERLAY_STYLE},,0,0,0,,{{\\an5\\pos({centre_x},{round(badge_y)})"
                f"\\bord0\\shad0\\1c{self.accent}{pop}\\p1}}{rounded_rect(badge_w, badge_h, badge_h / 2)}{{\\p0}}"
            )
            events.append(
                f"Dialogue: 5,{timing},{OVERLAY_STYLE},,0,0,0,,{{\\an5\\pos({centre_x},{round(badge_y)})"
                f"\\fs{ass_font_size(counter_em, self.family)}\\bord0\\shad0\\1c{self.ink}{pop}}}{text}"
            )
            lines = "\\N".join(wrap_title(item["label"], self._measure(label_em), width * LABEL_MAX_WIDTH))
            events.append(
                f"Dialogue: 5,{timing},{OVERLAY_STYLE},,0,0,0,,{{\\an8\\pos({centre_x},{round(label_top)})"
                f"\\fs{ass_font_size(label_em, self.family)}\\bord{max(2, round(4 * self.scale))}"
                f"\\shad{max(1, round(2 * self.scale))}{FADE}}}{lines}"
            )
        return events

    def rank_board(
        self, items: list[dict[str, Any]], width: int, band: tuple[float, float], slots: int,
    ) -> list[str]:
        """A board down the right side with ``slots`` ranks, best at the top; each
        label fills in when its item starts and is highlighted while it plays."""
        row_h = min(BOARD_ROW_PX * self.scale, (band[1] - band[0]) / slots)
        em = 0.52 * row_h
        size = ass_font_size(em, self.family)
        board_w = width * BOARD_WIDTH
        right = width - CLEARANCE * self.scale
        left = right - board_w
        number_w = text_width(f"{slots}.", self.font_file, em, 0) + 0.5 * em
        label_x = left + 0.35 * em + number_w
        label_w = right - label_x - 0.35 * em
        board_start = items[0]["start"]
        whole = f"{ass_time(board_start)},{ass_time(self.duration)}"

        events = [
            f"Dialogue: 3,{whole},{OVERLAY_STYLE},,0,0,0,,{{\\an7\\pos({round(left)},{round(band[0])})"
            f"\\bord0\\shad0{PANEL}{FADE}\\p1}}{rounded_rect(board_w, row_h * slots, 0.3 * row_h)}{{\\p0}}"
        ]
        for rank in range(1, slots + 1):
            middle = round(band[0] + (rank - 0.5) * row_h)
            events.append(
                f"Dialogue: 5,{whole},{OVERLAY_STYLE},,0,0,0,,{{\\an4\\pos({round(left + 0.35 * em)},{middle})"
                f"\\fs{size}\\bord0\\shad0\\1c{self.accent}{FADE}}}{rank}."
            )
        for item in items:
            top = band[0] + (item["rank"] - 1) * row_h
            middle = round(top + row_h / 2)
            label = self._fit(item["label"], em, label_w)
            active = f"{ass_time(item['start'])},{ass_time(item['end'])}"
            # The highlight sits behind the label only, so the rank beside it stays readable.
            pill_left = label_x - 0.25 * em
            events.append(
                f"Dialogue: 4,{active},{OVERLAY_STYLE},,0,0,0,,{{\\an7\\pos({round(pill_left)},{round(top + 0.08 * row_h)})"
                f"\\bord0\\shad0\\1c{self.accent}\\fad(120,0)\\p1}}"
                f"{rounded_rect(right - pill_left - 0.1 * em, 0.84 * row_h, 0.3 * row_h)}{{\\p0}}"
            )
            events.append(
                f"Dialogue: 5,{active},{OVERLAY_STYLE},,0,0,0,,{{\\an4\\pos({round(label_x)},{middle})"
                f"\\fs{size}\\bord0\\shad0\\1c{self.ink}\\fscx70\\fscy70\\t(0,160,\\fscx100\\fscy100)}}{label}"
            )
            if item["end"] < self.duration:
                events.append(
                    f"Dialogue: 5,{ass_time(item['end'])},{ass_time(self.duration)},{OVERLAY_STYLE},,0,0,0,,"
                    f"{{\\an4\\pos({round(label_x)},{middle})\\fs{size}\\bord{max(1, round(2 * self.scale))}"
                    f"\\shad0\\1c{WHITE}}}{label}"
                )
        return events

    def _measure(self, em: float):
        return lambda text: text_width(text, self.font_file, em, 0)

    def _fit(self, label: str, em: float, max_width: float) -> str:
        """``label`` cut back a word at a time, with an ellipsis, until it fits ``max_width``."""
        measure = self._measure(em)
        if measure(label) <= max_width:
            return label
        words = label.split()
        while len(words) > 1 and measure(" ".join(words) + "…") > max_width:
            words.pop()
        return " ".join(words) + "…"


def _band(
    occupied: list[tuple[float, float]], height: int, scale: float, needed: float,
) -> tuple[float, float]:
    """The topmost free stretch of the frame ``needed`` px tall, else the tallest one."""
    clearance = CLEARANCE * scale
    blocked = sorted((low - clearance, high + clearance) for low, high in occupied)
    free: list[tuple[float, float]] = []
    cursor = SAFE_TOP * height
    for low, high in blocked:
        if low > cursor:
            free.append((cursor, low))
        cursor = max(cursor, high)
    if cursor < SAFE_BOTTOM * height:
        free.append((cursor, SAFE_BOTTOM * height))
    free = [(low, min(high, SAFE_BOTTOM * height)) for low, high in free if high > low]
    if not free:
        return SAFE_TOP * height, SAFE_BOTTOM * height
    return next((band for band in free if band[1] - band[0] >= needed), max(free, key=lambda b: b[1] - b[0]))


def _label(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    text = " ".join(EMOJI.sub("", escape_ass(str(item.get("label") or ""))).split())
    return text if len(text) <= MAX_LABEL_CHARS else text[:MAX_LABEL_CHARS - 1].rstrip() + "…"


def _body_timing(
    item: dict[str, Any], clip_start: float, clip_end: float, spans: list[Span] | None, body: float,
) -> tuple[float, float] | None:
    """Where the item plays in the clip's body, in seconds from its start; None if cut out."""
    try:
        start = float(item["t"])
        end = max(float(item.get("end", start)), start + 0.01)
    except (KeyError, TypeError, ValueError):
        return None
    _, pieces = on_output_timeline([{"start": start, "end": end}], clip_start, clip_end, None, spans=spans)
    pieces = [(max(0.0, p["start"] - clip_start), min(body, p["end"] - clip_start)) for p in pieces]
    pieces = [(low, high) for low, high in pieces if high > low]
    if not pieces:
        return None
    return pieces[0][0], pieces[-1][1]


def _assign_ranks(items: list[dict[str, Any]]) -> None:
    """Keep each valid, unique rank; give the rest the free ranks counting down,
    so an unranked list reads as a countdown to the top pick. A clip of a
    longer ranking keeps its own ranks (10, 9, 8 of a top ten)."""
    count = len(items)
    taken: set[int] = set()
    for item in items:
        rank = item["rank"]
        if rank is None or not 1 <= rank <= max(count, MAX_RANK_SLOTS) or rank in taken:
            item["rank"] = None
        else:
            taken.add(rank)
    free = iter(sorted(set(range(1, count + 1)) - taken, reverse=True))
    for item in items:
        if item["rank"] is None:
            item["rank"] = next(free)


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
