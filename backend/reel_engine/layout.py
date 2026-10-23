"""Layout: the final box of every graphic and caption, measured on the finished cut.

Each item gets a box that covers no face (real face detection on frames of its own stretch), sits on the
plainest, stillest part of the frame (a detail map of edges and colour keeps it off food and products, a motion
map off gesturing hands), stays out of Instagram's UI zones, and never overlaps another item on screen at the
same time. Captions keep to two lanes (low, or high when the low lane is taken), so the eye always finds them. Words set behind
the person use the cut-out band finder; when only a narrow side band clears the person, the word is drawn
big in front instead.
"""

from __future__ import annotations

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
    "chart": (90, 900, 640, 750), "statement": (86, 908, 1152, 384), "progress": (150, 780, 80, 130), "wash": (0, W, H, 0),
    "flicker": (60, 960, 300, 780), "photocard": (190, 700, 600, 470), "hook": (60, 960, 300, 250),
}
FIXED = {"statement", "progress", "wash", "flicker", "accent", "effect"}
_detector = None


def look(video: str, start: float, end: float) -> tuple[list[tuple[int, int, int, int]], np.ndarray]:
    """Padded face boxes (output pixels) seen anywhere in ``start``..``end``, and the stretch's detail map."""
    import cv2

    from video_processor.face_detection import FaceDetector

    global _detector
    _detector = _detector or FaceDetector()
    boxes, maps, greys = [], [], []
    for share in (0.15, 0.5, 0.85):
        image = frame(video, start + (end - start) * share, 540)
        if image is None:
            continue
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        greys.append(cv2.resize(grey, (DETAIL_W, DETAIL_H), interpolation=cv2.INTER_AREA))
        edges = np.hypot(cv2.Sobel(grey, cv2.CV_32F, 1, 0), cv2.Sobel(grey, cv2.CV_32F, 0, 1))
        sat = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32) / 255
        detail = cv2.resize(np.clip(edges / 120, 0, 1) * 0.6 + sat * 0.4, (DETAIL_W, DETAIL_H), interpolation=cv2.INTER_AREA)
        maps.append(cv2.GaussianBlur(detail, (0, 0), 2))
        for face in _detector.detect(image):
            b = face.box
            px, py = b.width * FACE_PAD, b.height * FACE_PAD
            boxes.append((round((b.x - px) * W), round((b.y - py) * H), round((b.x + b.width + px) * W), round((b.y + b.height + py) * H)))
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


def default_box(kind: str, data: dict | None = None) -> list[int]:
    x, w, h, top = BOXES.get(kind, BOXES["two"])
    items = len((data or {}).get("items") or [])
    # Panels fit their rows (the renderer's row sizes): two items get a small card, not the five-item one.
    if kind == "list" and items:
        h = round(w * 0.12 + w * 0.15 * (items + (1.3 if (data or {}).get("title") else 0.2)))
    elif kind == "flow" and items:
        h = round(w * 0.16 * 1.6 * items)
    return [x, top, w, min(h, BOXES[kind][2]) if kind in BOXES else h]


def place(graphics: list[GraphicItem], captions: list[CaptionLine], video: str) -> None:
    """Set the box of every item; captions first (they sit where the eye already is), then graphics by start time."""
    taken: list[tuple[float, float, tuple[int, int, int, int]]] = []
    items: list[tuple[str, float, float, object]] = [("caption" if not c.payoff else "payoff", c.start, c.end, c) for c in captions]
    items += [(g.kind, g.start, g.end, g) for g in graphics]
    for kind, start, end, item in sorted(items, key=lambda i: (i[0] not in ("caption", "payoff"), i[1])):
        box = item.box if item.box else default_box(kind, getattr(item, "data", None))
        if kind in FIXED or getattr(item, "behind", False):
            item.box = box
            continue
        faces, detail = look(video, start, end)
        others = [b for a, z, b in taken if a < end and start < z]
        lanes = CAPTION_LANES if kind in ("caption", "payoff") else None
        box[1] = free_top(box, faces + others, detail, box[1], lanes)
        item.box = box
        taken.append((start, end, (box[0], box[1], box[0] + box[2], box[1] + box[3])))
