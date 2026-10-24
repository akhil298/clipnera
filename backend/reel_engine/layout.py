"""Layout: the final box of every graphic and caption, measured on the finished cut.

Each item gets a box that covers no face (real face detection on frames of its own stretch), sits on the
plainest, stillest part of the frame (a detail map of edges and colour keeps it off food and products, a motion
map off gesturing hands), stays out of Instagram's UI zones, and never overlaps another item on screen at the
same time. Captions keep to two lanes (low, or high when the low lane is taken), so the eye always finds them. Words set behind
the person use the cut-out band finder; when only a narrow side band clears the person, the word is drawn
big in front instead.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from core.logging_config import get_logger
from reel_engine.media import H, W, frame
from reel_engine.plan import CaptionLine, GraphicItem

log = get_logger(__name__)

SAFE_TOP, SAFE_BOTTOM = 230, 1650
FACE_PAD = 0.18
DETAIL_W, DETAIL_H = 96, 170
MOTION_WEIGHT = 1.5
# Caption lanes (top of the box): low first, high when a face, hands or another item fill the low one.
CAPTION_LANES = (1360, 1250, 330)
# Default size and preferred top (px) of each kind, before measuring.
BOXES = {
    "chapter": (70, 940, 270, 1300), "two": (100, 880, 220, 1320), "tag": (90, 900, 130, 1240), "cta": (150, 780, 260, 1220),
    "keyword": (90, 900, 270, 300), "name": (90, 900, 150, 1300), "count_up": (120, 840, 320, 1100),
    "caption": (80, 920, 210, 1380), "payoff": (70, 940, 280, 1320), "list": (90, 900, 760, 700), "flow": (90, 900, 820, 650),
    "chart": (90, 900, 640, 750), "statement": (86, 908, 440, 1190), "progress": (150, 780, 80, 130), "wash": (0, W, H, 0),
    "flicker": (60, 960, 300, 780), "photocard": (190, 700, 600, 470), "hook": (60, 960, 300, 250),
    "object": (300, 480, 440, 880),
}
FIXED = {"statement", "progress", "wash", "flicker", "accent", "effect"}
# A graphic may cover this share of a face or another item at most; past it, it is set smaller or at a side, else left
# out. Only these kinds are left out: the hook, titles and captions always stay.
CLEAR = 0.12
OPTIONAL = {"object", "photocard", "tag", "two", "count_up", "chart", "list", "flow", "name", "keyword", "image", "logo", "map", "ui"}
_detector = None


LOOK_GRID = 0.5  # seconds: frames are read on this grid and reused by every item that samples the same moment


@lru_cache(maxsize=1024)
def _frame_facts(video: str, t: float) -> tuple[tuple[tuple[int, int, int, int], ...], np.ndarray | None, np.ndarray | None]:
    """Padded face boxes, detail map and small grey frame at second ``t`` (read once, shared by every item)."""
    import cv2

    from video_processor.face_detection import FaceDetector

    global _detector
    image = frame(video, t, 540)
    if image is None:
        return (), None, None
    _detector = _detector or FaceDetector()
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    edges = np.hypot(cv2.Sobel(grey, cv2.CV_32F, 1, 0), cv2.Sobel(grey, cv2.CV_32F, 0, 1))
    sat = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32) / 255
    detail = cv2.GaussianBlur(cv2.resize(np.clip(edges / 120, 0, 1) * 0.6 + sat * 0.4, (DETAIL_W, DETAIL_H), interpolation=cv2.INTER_AREA),
                              (0, 0), 2)
    boxes = []
    for face in _detector.detect(image):
        b = face.box
        px, py = b.width * FACE_PAD, b.height * FACE_PAD
        boxes.append((round((b.x - px) * W), round((b.y - py) * H), round((b.x + b.width + px) * W), round((b.y + b.height + py) * H)))
    return tuple(boxes), detail, cv2.resize(grey, (DETAIL_W, DETAIL_H), interpolation=cv2.INTER_AREA)


def look(video: str, start: float, end: float) -> tuple[list[tuple[int, int, int, int]], np.ndarray]:
    """Padded face boxes (output pixels) seen anywhere in ``start``..``end``, and the stretch's detail map."""
    import cv2

    boxes, maps, greys = [], [], []
    for share in (0.15, 0.5, 0.85):
        t = round((start + (end - start) * share) / LOOK_GRID) * LOOK_GRID
        found, detail, grey = _frame_facts(video, t)
        if detail is None:
            continue
        boxes += list(found)
        maps.append(detail)
        greys.append(grey)
    detail = np.max(maps, axis=0) if maps else np.zeros((DETAIL_H, DETAIL_W), np.float32)
    if len(greys) > 1:
        # What changes across the stretch (hands, a demonstration) is busier than anything still.
        moving = np.max([np.abs(b - a) for a, b in zip(greys, greys[1:])], axis=0) / 40
        detail = detail + MOTION_WEIGHT * cv2.GaussianBlur(np.clip(moving, 0, 1).astype(np.float32), (0, 0), 2)
    return boxes, detail


def free_top(box: list[int], blocked: list[tuple[int, int, int, int]], detail: np.ndarray, preferred: int,
             tops: tuple[int, ...] | None = None) -> int:
    """The top for ``box``: never on a face or another item, then on the plainest part, then near ``preferred``;
    chosen from ``tops`` when given (caption lanes), else anywhere in the safe zone."""
    x, _, w, h = box
    sx, sy = DETAIL_W / W, DETAIL_H / H
    best = None
    candidates = [min(max(SAFE_TOP, t), SAFE_BOTTOM - h) for t in tops] if tops else range(SAFE_TOP, max(SAFE_TOP + 1, SAFE_BOTTOM - h + 1), 20)
    for top in candidates:
        overlap = sum(max(0, min(x + w, x1) - max(x, x0)) * max(0, min(top + h, y1) - max(top, y0)) for x0, y0, x1, y1 in blocked) / (w * h)
        busy = float(detail[int(top * sy):max(int(top * sy) + 1, int((top + h) * sy)), int(x * sx):max(int(x * sx) + 1, int((x + w) * sx))].mean())
        # Staying near the preferred top keeps placement consistent (and a reviewer's "move" sticks).
        cost = 100 * overlap + 25 * busy + 6 * abs(top - preferred) / H
        if best is None or cost < best[0]:
            best = (cost, top)
    return best[1]


def overlap(box: list[int], blocked: list[tuple[int, int, int, int]]) -> float:
    """The share of ``box`` lying on the ``blocked`` boxes."""
    x, y, w, h = box
    return sum(max(0, min(x + w, x1) - max(x, x0)) * max(0, min(y + h, y1) - max(y, y0)) for x0, y0, x1, y1 in blocked) / max(1, w * h)


def fit(box: list[int], blocked: list[tuple[int, int, int, int]], detail: np.ndarray, preferred: int) -> list[int] | None:
    """``box`` where it covers no face and no other item: as it is, else smaller (centred, then at either side), else
    None. A checklist the size of the frame once sat on the doctor's face, and an icon on the opening headline."""
    for scale in (1.0, 0.8, 0.65, 0.5):
        w, h = round(box[2] * scale), round(box[3] * scale)
        for x in dict.fromkeys((box[0] + (box[2] - w) // 2, 40, W - 40 - w)):
            candidate = [x, 0, w, h]
            candidate[1] = free_top(candidate, blocked, detail, preferred)
            if overlap(candidate, blocked) <= CLEAR:
                return candidate
    return None


def default_box(kind: str, data: dict | None = None) -> list[int]:
    x, w, h, top = BOXES.get(kind, BOXES["two"])
    items = len((data or {}).get("items") or [])
    # Panels fit their rows (the renderer's row sizes): two items get a small card, not the five-item one.
    if kind == "list" and items:
        h = round(w * 0.12 + w * 0.15 * (items + (1.3 if (data or {}).get("title") else 0.2)))
    elif kind == "flow" and items:
        h = round(w * 0.16 * 1.6 * items)
    return [x, top, w, min(h, BOXES[kind][2]) if kind in BOXES else h]


def band_box(box: list[int], picture: tuple[int, int, int, int]) -> list[int]:
    """``box`` fitted into the band above ``picture`` (the taller of the two clear bands when the top one is short)."""
    above, below = picture[1] - SAFE_TOP - 20, SAFE_BOTTOM - picture[3] - 20
    top, h = (SAFE_TOP, above) if above >= max(below, 260) else (picture[3] + 20, below)
    return [box[0], top, box[2], max(h, 120)]


def place(graphics: list[GraphicItem], captions: list[CaptionLine], video: str,
          picture: tuple[int, int, int, int] | None = None) -> None:
    """Set the box of every item; captions first (they sit where the eye already is), then graphics by start time.
    ``picture`` is the footage's strip when a reel shows each shot whole over a blurred copy: nothing is set on it, and
    statements move to the blurred band above it (else below). A graphic that fits nowhere clear (see ``fit``) is taken
    out of ``graphics``."""
    # An effect's card (a paper note, a panel) sits where its template puts it: other items keep off it.
    taken: list[tuple[float, float, tuple[int, int, int, int]]] = [
        (g.start, g.end, (x, y, x + w, y + h)) for g in graphics if g.kind == "effect"
        for x, y, w, h in [g.data.get("panel") or ()] if w]
    items: list[tuple[str, float, float, object]] = [("caption" if not c.payoff else "payoff", c.start, c.end, c) for c in captions]
    items += [(g.kind, g.start, g.end, g) for g in graphics]
    dropped: set[int] = set()
    # Captions first, then what must stay (hook, titles), then the optional graphics: those fit round the rest.
    for kind, start, end, item in sorted(items, key=lambda i: (i[0] not in ("caption", "payoff"), i[0] in OPTIONAL, i[1])):
        box = item.box if item.box else default_box(kind, getattr(item, "data", None))
        if picture and kind == "statement":
            box = band_box(box, picture)
            # In its band the statement is an ordinary box: later items keep off it.
            taken.append((start, end, (box[0], box[1], box[0] + box[2], box[1] + box[3])))
        if kind in FIXED or getattr(item, "behind", False):
            item.box = box
            continue
        faces, detail = look(video, start, end)
        others = [b for a, z, b in taken if a < end and start < z] + ([picture] if picture else [])
        lanes = CAPTION_LANES if kind in ("caption", "payoff") else None
        if kind in OPTIONAL:
            placed = fit(box, faces + others, detail, box[1])
            if placed is None:
                dropped.add(id(item))
                continue
            box = placed
        else:
            box[1] = free_top(box, faces + others, detail, box[1], lanes)
        item.box = box
        taken.append((start, end, (box[0], box[1], box[0] + box[2], box[1] + box[3])))
    if dropped:
        log.info("Layout: %d graphics left out, nowhere clear of faces and other items", len(dropped))
        graphics[:] = [g for g in graphics if id(g) not in dropped]
