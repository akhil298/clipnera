from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

LOG = logging.getLogger(__name__)


SUPPORTED_LAYOUTS = [
    "single_subject",
    "two_subjects_top_bottom",
    "two_subjects_left_right",
    "multi_subject_grid",
    "stacked_multi_subject",
    "gaming_with_facecam",
    "gameplay_only",
    "speaker_plus_screen",
    "podcast_interview",
    "screen_share",
    "presentation",
    "reaction_video",
    "mixed_layout",
    "unknown",
]


@dataclass
class Scene:
    start: float = 0.0
    end: float = 0.0
    frames: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LayoutDecision:
    layout: str = "unknown"
    confidence: float = 0.0
    scene_start: float = 0.0
    scene_end: float = 0.0
    evidence: list[str] = field(default_factory=list)


class LayoutRegistry:
    _detectors: dict[str, Any] = {}

    @classmethod
    def register(cls, layout_name: str) -> Any:
        def decorator(func: Any) -> Any:
            cls._detectors[layout_name] = func
            return func
        return decorator

    @classmethod
    def detect(cls, layout_name: str, scene: Scene) -> tuple[float, list[str]]:
        detector = cls._detectors.get(layout_name)
        if detector is None:
            return 0.0, []
        try:
            return detector(scene)
        except Exception as exc:
            LOG.debug("Layout detector %s failed: %s", layout_name, exc)
            return 0.0, []

    @classmethod
    def all_detectors(cls) -> dict[str, Any]:
        return dict(cls._detectors)


def _normalize_box(box: dict[str, Any] | None) -> dict[str, float] | None:
    if not box or not isinstance(box, dict):
        return None
    try:
        x = float(box.get("x", 0.0))
        y = float(box.get("y", 0.0))
        w = float(box.get("width", 0.0))
        h = float(box.get("height", 0.0))
        if max(x, w) > 1.0:
            x /= max(1.0, abs(float(box.get("frame_width", 1.0)) or 1.0))
            w /= max(1.0, abs(float(box.get("frame_width", 1.0)) or 1.0))
        if max(y, h) > 1.0:
            y /= max(1.0, abs(float(box.get("frame_height", 1.0)) or 1.0))
            h /= max(1.0, abs(float(box.get("frame_height", 1.0)) or 1.0))
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        w = min(1.0 - x, max(0.0, w))
        h = min(1.0 - y, max(0.0, h))
        return {"x": round(x, 6), "y": round(y, 6), "width": round(w, 6), "height": round(h, 6)}
    except (TypeError, ValueError):
        return None


def _collect_subjects(frame: dict[str, Any]) -> list[dict[str, Any]]:
    subjects: list[dict[str, Any]] = []
    for key in ("subjects", "faces", "objects"):
        raw = frame.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("bounding_box"):
                    subjects.append(item)
    return subjects


def _all_normalized_boxes(scene: Scene) -> list[dict[str, float]]:
    boxes: list[dict[str, float]] = []
    for frame in scene.frames:
        for subject in _collect_subjects(frame):
            nb = _normalize_box(subject.get("bounding_box"))
            if nb and nb["width"] > 0.0 and nb["height"] > 0.0:
                boxes.append(nb)
    return boxes


def _aspect_ratios_of(boxes: list[dict[str, float]]) -> list[float]:
    return [max(1e-6, b["width"]) / max(1e-6, b["height"]) for b in boxes]


def _centers(boxes: list[dict[str, float]]) -> list[tuple[float, float]]:
    return [(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2) for b in boxes]


def _frame_count(scene: Scene) -> int:
    return len(scene.frames)


def _is_gaming_content(scene: Scene) -> bool:
    for frame in scene.frames:
        cat = str(frame.get("content_category", "")).lower()
        if "game" in cat:
            return True
        desc = str(frame.get("description", "")).lower()
        if any(kw in desc for kw in ("gameplay", "gaming", "game", "playing")):
            return True
        scene_label = str(frame.get("scene", "")).lower()
        if any(kw in scene_label for kw in ("game", "gameplay")):
            return True
    return False


def _has_screen(scene: Scene) -> bool:
    for frame in scene.frames:
        objects = frame.get("objects", []) or []
        subjects = frame.get("subjects", []) or []
        text = frame.get("on_screen_text", []) or []
        total_items = len(objects) + len(subjects) + len(text)
        for item in objects + subjects:
            label = str(item.get("label", "")).lower()
            if any(kw in label for kw in ("screen", "monitor", "display", "laptop", "desktop", "presentation")):
                return True
        if len(text) >= 2:
            return True
        desc = str(frame.get("description", "")).lower()
        if any(kw in desc for kw in ("screen share", "presentation", "slide", "slideshow")):
            return True
    return False


def _speaker_count(scene: Scene) -> int:
    speakers: set[str] = set()
    for frame in scene.frames:
        for subject in (frame.get("subjects", []) or []):
            sp = subject.get("speaker") or subject.get("speaker_id")
            if sp:
                speakers.add(str(sp))
            if subject.get("is_speaker"):
                speakers.add(str(subject.get("label", "")))
    return max(1, len(speakers))


@LayoutRegistry.register("single_subject")
def _detect_single_subject(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 1:
        return 0.0, []
    ev: list[str] = []
    cx_all = [(b["x"] + b["width"] / 2) for b in boxes]
    cy_all = [(b["y"] + b["height"] / 2) for b in boxes]
    x_var = _variance(cx_all)
    y_var = _variance(cy_all)
    areas = [b["width"] * b["height"] for b in boxes]
    area_var = _variance(areas)
    major_count = sum(1 for a in areas if a > 0.25)
    if major_count > 2:
        return 0.0, ["too_many_large_subjects"]
    stability = 1.0 / (1.0 + x_var + y_var + area_var)
    score = max(0.0, min(1.0, stability * (1.0 + 0.5 * len(boxes) / max(1, _frame_count(scene)))))
    ev.append(f"stability={stability:.3f}")
    ev.append(f"subject_count={len(set(tuple(sorted(b.items())) for b in boxes))}")
    return score, ev


@LayoutRegistry.register("two_subjects_top_bottom")
def _detect_two_subjects_top_bottom(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 4:
        return 0.0, []
    ev: list[str] = []
    clusters = _simple_kmeans(boxes, k=2)
    if clusters is None or len(clusters) < 2:
        return 0.0, []
    cy_centers = [
        sum(b["y"] + b["height"] / 2 for b in c) / max(1, len(c))
        for c in clusters
    ]
    vertical_gap = abs(cy_centers[0] - cy_centers[1])
    vertical_gap_ok = vertical_gap > 0.25
    all_x_centers = [b["x"] + b["width"] / 2 for c in clusters for b in c]
    x_var = _variance(all_x_centers)
    horizontally_aligned = x_var < 0.08
    if not (vertical_gap_ok and horizontally_aligned):
        return 0.0, [f"vgap={vertical_gap:.3f}", f"xvar={x_var:.3f}"]
    score = min(1.0, 0.5 + vertical_gap + 1.0 / (1.0 + x_var))
    ev.extend([f"variance_y={vertical_gap:.3f}", f"h_alignment_var={x_var:.3f}", f"clusters={len(clusters)}"])
    return score, ev


@LayoutRegistry.register("two_subjects_left_right")
def _detect_two_subjects_left_right(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 4:
        return 0.0, []
    ev: list[str] = []
    clusters = _simple_kmeans(boxes, k=2)
    if clusters is None or len(clusters) < 2:
        return 0.0, []
    cx_centers = [
        sum(b["x"] + b["width"] / 2 for b in c) / max(1, len(c))
        for c in clusters
    ]
    horizontal_gap = abs(cx_centers[0] - cx_centers[1])
    horizontal_gap_ok = horizontal_gap > 0.25
    all_y_centers = [b["y"] + b["height"] / 2 for c in clusters for b in c]
    y_var = _variance(all_y_centers)
    vertically_aligned = y_var < 0.12
    if not (horizontal_gap_ok and vertically_aligned):
        return 0.0, [f"hgap={horizontal_gap:.3f}", f"yvar={y_var:.3f}"]
    score = min(1.0, 0.5 + horizontal_gap + 1.0 / (1.0 + y_var))
    ev.extend([f"variance_x={horizontal_gap:.3f}", f"v_alignment_var={y_var:.3f}"])
    return score, ev


@LayoutRegistry.register("multi_subject_grid")
def _detect_multi_subject_grid(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 6:
        return 0.0, []
    ev: list[str] = []
    clusters = _simple_kmeans(boxes, k=min(4, len(boxes)))
    if clusters is None or len(clusters) < 3:
        return 0.0, []
    cx = [sum(b["x"] + b["width"] / 2 for b in c) / max(1, len(c)) for c in clusters]
    cy = [sum(b["y"] + b["height"] / 2 for b in c) / max(1, len(c)) for c in clusters]
    x_var = _variance(cx)
    y_var = _variance(cy)
    if x_var < 0.03 or y_var < 0.03:
        return 0.0, []
    score = min(1.0, 0.4 + 0.3 * len(clusters) + 1.0 / (1.0 + x_var + y_var))
    ev.extend([f"clusters={len(clusters)}", f"x_var={x_var:.3f}", f"y_var={y_var:.3f}"])
    return score, ev


@LayoutRegistry.register("stacked_multi_subject")
def _detect_stacked_multi_subject(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 3:
        return 0.0, []
    ev: list[str] = []
    centers = _centers(boxes)
    ys = [c[1] for c in centers]
    y_range = max(ys) - min(ys) if ys else 0.0
    xs = [c[0] for c in centers]
    x_var = _variance(xs)
    if y_range < 0.2 or x_var > 0.15:
        return 0.0, []
    score = min(1.0, 0.4 + y_range + 0.5 / (1.0 + x_var))
    ev.extend([f"y_range={y_range:.3f}", f"x_var={x_var:.3f}", f"subjects={len(set(tuple(sorted(b.items())) for b in boxes))}"])
    return score, ev


@LayoutRegistry.register("gaming_with_facecam")
def _detect_gaming_with_facecam(scene: Scene) -> tuple[float, list[str]]:
    if not _is_gaming_content(scene):
        return 0.0, []
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 2:
        return 0.0, []
    ev: list[str] = []
    face_like = [b for b in boxes if (b["width"] * b["height"]) < 0.30]
    large_like = [b for b in boxes if (b["width"] * b["height"]) >= 0.20]
    if not face_like or not large_like:
        return 0.0, []
    face_top = [b for b in face_like if b["y"] < 0.4]
    game_bottom = [b for b in large_like if b["y"] >= 0.3]
    if not face_top or not game_bottom:
        return 0.0, []
    score = 0.5 + 0.3 * min(1.0, len(face_top) / 3) + 0.2 * min(1.0, len(game_bottom) / 2)
    ev.extend([f"facecam_frames={len(face_top)}", f"gameplay_frames={len(game_bottom)}", "content_category=gaming"])
    return min(1.0, score), ev


@LayoutRegistry.register("gameplay_only")
def _detect_gameplay_only(scene: Scene) -> tuple[float, list[str]]:
    if not _is_gaming_content(scene):
        return 0.0, []
    boxes = _all_normalized_boxes(scene)
    if not boxes:
        return 0.0, []
    ev: list[str] = []
    avg_area = sum(b["width"] * b["height"] for b in boxes) / len(boxes)
    face_small = sum(1 for b in boxes if (b["width"] * b["height"]) < 0.10)
    if avg_area > 0.50 and face_small / max(1, len(boxes)) < 0.3:
        score = 0.5 + 0.5 * min(1.0, avg_area)
        ev.append(f"avg_subject_area={avg_area:.3f}")
        ev.append("no_significant_facecam")
        return min(1.0, score), ev
    return 0.0, []


@LayoutRegistry.register("speaker_plus_screen")
def _detect_speaker_plus_screen(scene: Scene) -> tuple[float, list[str]]:
    if not _has_screen(scene):
        return 0.0, []
    boxes = _all_normalized_boxes(scene)
    ev: list[str] = []
    speaker_boxes = [b for b in boxes if b["width"] < 0.5 and b["height"] < 0.7]
    screen_like = [b for b in boxes if b["width"] > 0.4 or b["height"] > 0.4]
    has_speaker = len(speaker_boxes) >= 1
    has_screen = len(screen_like) >= 1
    if not (has_speaker and has_screen):
        return 0.0, []
    speaker_x = [b["x"] for b in speaker_boxes]
    screen_x = [b["x"] for b in screen_like]
    separated = (
        max(speaker_x) < min(screen_x) or max(screen_x) < min(speaker_x)
        if speaker_x and screen_x
        else True
    )
    if not separated:
        return 0.0, []
    score = 0.6 + 0.2 * min(1.0, len(speaker_boxes) / 3) + 0.2 * min(1.0, len(screen_like) / 2)
    ev.extend([f"speaker_boxes={len(speaker_boxes)}", f"screen_boxes={len(screen_like)}", "has_screen"])
    return min(1.0, score), ev


@LayoutRegistry.register("podcast_interview")
def _detect_podcast_interview(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    ev: list[str] = []
    spk = _speaker_count(scene)
    if spk < 2:
        return 0.0, []
    clusters = _simple_kmeans(boxes, k=min(spk, 4)) if len(boxes) >= 4 else None
    if clusters is None or len(clusters) < 2:
        return 0.0, []
    cx = [sum(b["x"] + b["width"] / 2 for b in c) / max(1, len(c)) for c in clusters]
    cy = [sum(b["y"] + b["height"] / 2 for b in c) / max(1, len(c)) for c in clusters]
    x_var = _variance(cx)
    y_var = _variance(cy)
    if x_var > 0.25 and y_var > 0.25:
        return 0.0, []
    score = 0.5 + 0.2 * min(1.0, spk / 4) + 0.3 / (1.0 + x_var + y_var)
    ev.extend([f"speakers={spk}", f"x_var={x_var:.3f}", f"y_var={y_var:.3f}"])
    return min(1.0, score), ev


@LayoutRegistry.register("screen_share")
def _detect_screen_share(scene: Scene) -> tuple[float, list[str]]:
    if not _has_screen(scene):
        return 0.0, []
    boxes = _all_normalized_boxes(scene)
    ev: list[str] = []
    screen_boxes = [b for b in boxes if (b["width"] * b["height"]) > 0.50]
    if not screen_boxes:
        return 0.0, []
    dominant = sum(1 for b in screen_boxes if (b["width"] * b["height"]) > 0.70) / max(1, len(screen_boxes))
    score = 0.5 + 0.5 * min(1.0, dominant)
    ev.append(f"dominant_screen_boxes={dominant:.2f}")
    return min(1.0, score), ev


@LayoutRegistry.register("presentation")
def _detect_presentation(scene: Scene) -> tuple[float, list[str]]:
    if not _has_screen(scene):
        return 0.0, []
    boxes = _all_normalized_boxes(scene)
    ev: list[str] = []
    speaker_boxes = [b for b in boxes if (b["width"] * b["height"]) < 0.30]
    text_regions = 0
    for frame in scene.frames:
        text_regions += len(frame.get("on_screen_text", []) or [])
    if not speaker_boxes or text_regions < len(scene.frames) * 0.3:
        return 0.0, []
    score = 0.4 + 0.3 * min(1.0, len(speaker_boxes) / 5) + 0.3 * min(1.0, text_regions / max(1, len(scene.frames)))
    ev.extend([f"speaker_boxes={len(speaker_boxes)}", f"text_regions={text_regions}"])
    return min(1.0, score), ev


@LayoutRegistry.register("reaction_video")
def _detect_reaction_video(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 2:
        return 0.0, []
    ev: list[str] = []
    faces = 0
    for frame in scene.frames:
        faces += len(frame.get("faces", []) or [])
    small_boxes = sum(1 for b in boxes if (b["width"] * b["height"]) < 0.20)
    if faces < 2 or small_boxes / max(1, len(boxes)) < 0.4:
        return 0.0, []
    score = 0.5 + 0.3 * min(1.0, faces / max(1, len(scene.frames))) + 0.2 * min(1.0, small_boxes / max(1, len(boxes)))
    ev.extend([f"faces={faces}", f"small_subject_ratio={small_boxes / max(1, len(boxes)):.3f}"])
    return min(1.0, score), ev


@LayoutRegistry.register("mixed_layout")
def _detect_mixed_layout(scene: Scene) -> tuple[float, list[str]]:
    boxes = _all_normalized_boxes(scene)
    if len(boxes) < 3:
        return 0.0, []
    ev: list[str] = []
    ev.append("mixed_subject_positions")
    score = 0.3 + 0.1 * min(1.0, len({tuple(sorted(b.items())) for b in boxes}) / max(1, len(boxes)))
    return min(1.0, score), ev


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _simple_kmeans(boxes: list[dict[str, float]], k: int = 2, iterations: int = 8) -> list[list[dict[str, float]]] | None:
    if not boxes or k < 1 or k > len(boxes):
        return None
    rng = [0.0, 1.0]
    centroids: list[tuple[float, float]] = []
    for i in range(k):
        b = boxes[i % len(boxes)]
        centroids.append((b["x"] + b["width"] / 2, b["y"] + b["height"] / 2))
    for _ in range(iterations):
        clusters: list[list[dict[str, float]]] = [[] for _ in range(k)]
        for b in boxes:
            cx = b["x"] + b["width"] / 2
            cy = b["y"] + b["height"] / 2
            dists = [((cx - cc[0]) ** 2 + (cy - cc[1]) ** 2) for cc in centroids]
            nearest = min(range(k), key=lambda i: dists[i])
            clusters[nearest].append(b)
        new_centroids: list[tuple[float, float]] = []
        for c in clusters:
            if c:
                mx = sum(b["x"] + b["width"] / 2 for b in c) / len(c)
                my = sum(b["y"] + b["height"] / 2 for b in c) / len(c)
                new_centroids.append((mx, my))
            else:
                new_centroids.append(centroids[len(new_centroids)])
        centroids = new_centroids
    return [c for c in clusters if c]


def _segment_scenes(frames: list[dict[str, Any]], scene_changes: list[float] | None = None) -> list[Scene]:
    scene_changes = scene_changes or []
    change_points = sorted({0.0, *[float(t) for t in scene_changes if isinstance(t, (int, float))]})
    if not change_points:
        change_points = [0.0]
    max_ts = max((float(f.get("timestamp", 0.0)) for f in frames), default=0.0)
    boundaries: list[tuple[float, float]] = []
    for i in range(len(change_points)):
        start = change_points[i]
        end = change_points[i + 1] if i + 1 < len(change_points) else max_ts + 5.0
        boundaries.append((start, min(end, max_ts + 5.0)))
    scene_map: list[Scene] = [Scene(start=s, end=e) for s, e in boundaries]
    for frame in frames:
        ts = float(frame.get("timestamp", 0.0))
        for scene in scene_map:
            if scene.start <= ts < scene.end:
                scene.frames.append(frame)
                break
        else:
            scene_map[-1].frames.append(frame)
    return scene_map


class LayoutAnalyzer:
    def __init__(self, min_confidence: float = 0.35) -> None:
        self._min_confidence = min_confidence
        self._last_stable_layout: str = "unknown"

    def analyze_scenes(
        self,
        frames: list[dict[str, Any]],
        scene_changes: list[float] | None = None,
        content_category: str | None = None,
    ) -> list[LayoutDecision]:
        if not frames:
            return [LayoutDecision(layout="unknown", confidence=0.0, scene_start=0.0, scene_end=float("inf"), evidence=["no_frames"])]
        scenes = _segment_scenes(frames, scene_changes)
        if not scenes:
            return [LayoutDecision(layout="unknown", confidence=0.0, scene_start=0.0, scene_end=float("inf"), evidence=["no_scenes"])]
        decisions: list[LayoutDecision] = []
        for scene in scenes:
            decision = self._analyze_scene(scene, content_category)
            if decision.confidence < self._min_confidence:
                fallback = self._last_stable_layout if self._last_stable_layout != "unknown" else "unknown"
                LOG.debug(
                    "Low layout confidence %.3f, using fallback %s",
                    decision.confidence, fallback,
                    extra={"scene_start": scene.start, "scene_end": scene.end, "fallback_layout": fallback},
                )
                decision.layout = fallback
                decision.evidence.append(f"low_confidence_fallback={fallback}")
            else:
                self._last_stable_layout = decision.layout
            if decision.layout == "unknown":
                decision.evidence.append("no_reliable_layout_detected")
            decisions.append(decision)
        return decisions

    def _analyze_scene(self, scene: Scene, content_category: str | None) -> LayoutDecision:
        candidates: dict[str, tuple[float, list[str]]] = {}
        detectors = LayoutRegistry.all_detectors()
        for layout_name, detector in detectors.items():
            score, evidence = detector(scene)
            if score > 0.0:
                candidates[layout_name] = (score, evidence)
        if not candidates:
            return LayoutDecision(
                layout="unknown", confidence=0.0,
                scene_start=scene.start, scene_end=scene.end,
                evidence=["no_candidate_matched"],
            )
        best_layout, (best_score, best_evidence) = max(candidates.items(), key=lambda x: x[1][0])
        total = sum(s for s, _ in candidates.values()) or 1.0
        normalized_conf = min(1.0, best_score / total)
        clamped_conf = min(1.0, max(0.0, normalized_conf))
        evidence = list(best_evidence)
        evidence.append(f"candidates={list(candidates.keys())}")
        LOG.debug(
            "Layout detected: %s (conf=%.3f) for scene %.1f-%.1f",
            best_layout, clamped_conf, scene.start, scene.end,
            extra={
                "layout": best_layout,
                "confidence": clamped_conf,
                "scene_start": scene.start,
                "scene_end": scene.end,
                "evidence": evidence,
                "content_category": content_category,
            },
        )
        return LayoutDecision(
            layout=best_layout,
            confidence=round(clamped_conf, 4),
            scene_start=scene.start,
            scene_end=scene.end,
            evidence=evidence,
        )
