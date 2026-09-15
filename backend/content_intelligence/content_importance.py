from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

LOG = logging.getLogger(__name__)


@dataclass
class RegionImportance:
    region_type: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    weight: float = 0.0
    reason: str = ""


@dataclass
class ImportanceMap:
    regions: list[RegionImportance] = field(default_factory=list)
    primary_region: RegionImportance | None = None
    scene_type: str = "unknown"
    content_category: str = "unknown"


def _normalize_box(box: dict[str, Any] | None) -> dict[str, float] | None:
    if not box or not isinstance(box, dict):
        return None
    try:
        x = float(box.get("x", 0.0))
        y = float(box.get("y", 0.0))
        w = float(box.get("width", 0.0))
        h = float(box.get("height", 0.0))
        if max(x, w) > 1.0:
            fw = float(box.get("frame_width", 1.0)) or 1.0
            fh = float(box.get("frame_height", 1.0)) or 1.0
            x, w = x / fw, w / fw
            y, h = y / fh, h / fh
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        w = min(1.0 - x, max(0.0, w))
        h = min(1.0 - y, max(0.0, h))
        return {"x": round(x, 6), "y": round(y, 6), "width": round(w, 6), "height": round(h, 6)}
    except (TypeError, ValueError):
        return None


def _box_area(box: dict[str, float]) -> float:
    return max(1e-6, box["width"]) * max(1e-6, box["height"])


def _detect_content_category(frames: list[dict[str, Any]]) -> str:
    categories: dict[str, int] = {}
    for frame in frames:
        cat = str(frame.get("content_category", "")).lower()
        if cat:
            categories[cat] = categories.get(cat, 0) + 1
        desc = str(frame.get("description", "")).lower()
        if any(kw in desc for kw in ("game", "gameplay", "gaming")):
            categories["gaming"] = categories.get("gaming", 0) + 1
        if any(kw in desc for kw in ("podcast", "interview", "talk show")):
            categories["podcast_interview"] = categories.get("podcast_interview", 0) + 1
        if any(kw in desc for kw in ("screen share", "slideshow", "presentation")):
            categories["screen_share"] = categories.get("screen_share", 0) + 1
    if not categories:
        return "unknown"
    return max(categories, key=categories.get)


def _detect_scene_type(frames: list[dict[str, Any]], content_category: str) -> str:
    if content_category == "gaming":
        return "gameplay"
    if content_category == "podcast_interview":
        return "interview"
    if content_category in ("screen_share", "presentation", "tutorial_educational"):
        return "presentation"
    if content_category == "reaction":
        return "reaction"
    screen_count = 0
    face_count = 0
    for frame in frames:
        objects = frame.get("objects", []) or []
        for item in objects:
            label = str(item.get("label", "")).lower()
            if any(kw in label for kw in ("screen", "monitor", "display", "laptop")):
                screen_count += 1
        face_count += len(frame.get("faces", []) or [])
    if screen_count > face_count * 2:
        return "screen_share"
    if face_count >= 1:
        return "talking_head"
    return "unknown"


class ContentImportanceAnalyzer:
    def __init__(self) -> None:
        self._weights: dict[str, dict[str, float]] = {
            "gameplay": {
                "gameplay": 1.0,
                "facecam": 0.5,
                "speaker": 0.6,
                "person_body": 0.4,
                "screen": 0.4,
                "important_object": 0.5,
                "text": 0.3,
                "reaction": 0.3,
            },
            "interview": {
                "speaker": 1.0,
                "facecam": 0.9,
                "person_body": 0.7,
                "screen": 0.4,
                "important_object": 0.3,
                "text": 0.4,
                "reaction": 0.5,
            },
            "talking_head": {
                "facecam": 1.0,
                "speaker": 0.9,
                "person_body": 0.7,
                "screen": 0.3,
                "important_object": 0.3,
                "text": 0.4,
                "reaction": 0.3,
            },
            "screen_share": {
                "screen": 1.0,
                "important_object": 0.6,
                "text": 0.9,
                "speaker": 0.5,
                "facecam": 0.4,
                "person_body": 0.3,
                "reaction": 0.2,
            },
            "presentation": {
                "screen": 0.9,
                "text": 0.9,
                "speaker": 0.6,
                "facecam": 0.5,
                "important_object": 0.5,
                "reaction": 0.3,
            },
            "reaction": {
                "reaction": 1.0,
                "facecam": 0.9,
                "screen": 0.7,
                "speaker": 0.7,
                "text": 0.6,
                "important_object": 0.5,
            },
        }

    def analyze(
        self,
        scene: dict[str, Any],
        content_category: str | None = None,
    ) -> ImportanceMap:
        frames: list[dict[str, Any]] = scene.get("frames") or scene.get("frame_analyses") or []
        if not frames:
            return ImportanceMap(
                regions=[], primary_region=None,
                scene_type="unknown", content_category=content_category or "unknown",
            )
        cat = content_category or _detect_content_category(frames)
        scene_type = _detect_scene_type(frames, cat)
        weights = self._weights.get(scene_type, self._weights.get("talking_head", {}))
        region_map: dict[str, RegionImportance] = {}
        active_speaker_box = self._find_active_speaker(frames)
        if active_speaker_box:
            region_map["speaker"] = RegionImportance(
                region_type="speaker",
                x=active_speaker_box["x"],
                y=active_speaker_box["y"],
                width=active_speaker_box["width"],
                height=active_speaker_box["height"],
                weight=weights.get("speaker", 0.5),
                reason="active_speaker_detected",
            )
        face_box = self._find_dominant_face(frames)
        if face_box:
            region_map["facecam"] = RegionImportance(
                region_type="facecam",
                x=face_box["x"],
                y=face_box["y"],
                width=face_box["width"],
                height=face_box["height"],
                weight=weights.get("facecam", 0.5),
                reason="face_detected",
            )
        screen_box = self._find_screen_region(frames)
        if screen_box:
            region_map["screen"] = RegionImportance(
                region_type="screen",
                x=screen_box["x"],
                y=screen_box["y"],
                width=screen_box["width"],
                height=screen_box["height"],
                weight=weights.get("screen", 0.5),
                reason="screen_region_detected",
            )
        body_box = self._find_body_region(frames)
        if body_box:
            region_map["person_body"] = RegionImportance(
                region_type="person_body",
                x=body_box["x"],
                y=body_box["y"],
                width=body_box["width"],
                height=body_box["height"],
                weight=weights.get("person_body", 0.4),
                reason="person_body_detected",
            )
        text_regions = self._find_text_regions(frames)
        if text_regions:
            region_map["text"] = RegionImportance(
                region_type="text",
                x=text_regions["x"],
                y=text_regions["y"],
                width=text_regions["width"],
                height=text_regions["height"],
                weight=weights.get("text", 0.3),
                reason="on_screen_text_detected",
            )
        important_objects = self._find_important_objects(frames)
        if important_objects:
            region_map["important_object"] = RegionImportance(
                region_type="important_object",
                x=important_objects["x"],
                y=important_objects["y"],
                width=important_objects["width"],
                height=important_objects["height"],
                weight=weights.get("important_object", 0.3),
                reason="important_objects_detected",
            )
        reaction_box = self._find_reaction_region(frames)
        if reaction_box:
            region_map["reaction"] = RegionImportance(
                region_type="reaction",
                x=reaction_box["x"],
                y=reaction_box["y"],
                width=reaction_box["width"],
                height=reaction_box["height"],
                weight=weights.get("reaction", 0.3),
                reason="reaction_region_detected",
            )
        primary = max(region_map.values(), key=lambda r: r.weight) if region_map else None
        LOG.debug(
            "Importance map built",
            extra={
                "scene_type": scene_type,
                "content_category": cat,
                "regions": len(region_map),
                "primary_region": primary.region_type if primary else None,
                "primary_weight": primary.weight if primary else 0.0,
            },
        )
        return ImportanceMap(
            regions=list(region_map.values()),
            primary_region=primary,
            scene_type=scene_type,
            content_category=cat,
        )

    def _find_active_speaker(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        boxes: list[dict[str, float]] = []
        for frame in frames:
            subjects = frame.get("subjects", []) or []
            for s in subjects:
                if s.get("is_speaker"):
                    nb = _normalize_box(s.get("bounding_box"))
                    if nb and nb["width"] > 0.01 and nb["height"] > 0.01:
                        boxes.append(nb)
                speaker_name = s.get("speaker") or frame.get("speaker")
                if speaker_name and s.get("bounding_box"):
                    nb = _normalize_box(s.get("bounding_box"))
                    if nb and nb["width"] > 0.01 and nb["height"] > 0.01:
                        boxes.append(nb)
        if not boxes:
            return None
        areas = [_box_area(b) for b in boxes]
        largest_idx = max(range(len(boxes)), key=lambda i: areas[i])
        return boxes[largest_idx]

    def _find_dominant_face(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        boxes: list[dict[str, float]] = []
        for frame in frames:
            for face in frame.get("faces", []) or []:
                nb = _normalize_box(face.get("bounding_box"))
                if nb and nb["width"] > 0.01 and nb["height"] > 0.01:
                    boxes.append(nb)
        if not boxes:
            return None
        areas = [_box_area(b) for b in boxes]
        largest_idx = max(range(len(boxes)), key=lambda i: areas[i])
        return boxes[largest_idx]

    def _find_screen_region(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        best: dict[str, float] | None = None
        best_area = 0.0
        for frame in frames:
            for item in (frame.get("objects", []) or []) + (frame.get("subjects", []) or []):
                label = str(item.get("label", "")).lower()
                if any(kw in label for kw in ("screen", "monitor", "display", "laptop", "desktop", "presentation")):
                    nb = _normalize_box(item.get("bounding_box"))
                    if nb and _box_area(nb) > best_area:
                        best = nb
                        best_area = _box_area(nb)
        return best

    def _find_body_region(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        boxes: list[dict[str, float]] = []
        for frame in frames:
            for subject in (frame.get("subjects", []) or []):
                label = str(subject.get("label", "")).lower()
                if any(kw in label for kw in ("person", "body", "speaker")):
                    nb = _normalize_box(subject.get("bounding_box"))
                    if nb and nb["width"] > 0.1 and nb["height"] > 0.15:
                        boxes.append(nb)
        if not boxes:
            return None
        areas = [_box_area(b) for b in boxes]
        largest_idx = max(range(len(boxes)), key=lambda i: areas[i])
        return boxes[largest_idx]

    def _find_text_regions(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        all_boxes: list[dict[str, float]] = []
        for frame in frames:
            text_items = frame.get("on_screen_text", []) or []
            for item in text_items:
                if isinstance(item, dict):
                    nb = _normalize_box(item.get("bounding_box"))
                    if nb:
                        all_boxes.append(nb)
        if not all_boxes:
            return None
        min_x = min(b["x"] for b in all_boxes)
        min_y = min(b["y"] for b in all_boxes)
        max_x = max(b["x"] + b["width"] for b in all_boxes)
        max_y = max(b["y"] + b["height"] for b in all_boxes)
        return {
            "x": round(min_x, 6),
            "y": round(min_y, 6),
            "width": round(max(1e-6, max_x - min_x), 6),
            "height": round(max(1e-6, max_y - min_y), 6),
        }

    def _find_important_objects(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        best: dict[str, float] | None = None
        best_area = 0.0
        for frame in frames:
            for item in (frame.get("objects", []) or []) + (frame.get("subjects", []) or []):
                label = str(item.get("label", "")).lower()
                if any(kw in label for kw in ("game", "controller", "ball", "car", "gun", "sword", "important", "key")):
                    nb = _normalize_box(item.get("bounding_box"))
                    if nb and _box_area(nb) > best_area:
                        best = nb
                        best_area = _box_area(nb)
        return best

    def _find_reaction_region(self, frames: list[dict[str, Any]]) -> dict[str, float] | None:
        boxes: list[dict[str, float]] = []
        for frame in frames:
            faces = frame.get("faces", []) or []
            for face in faces:
                nb = _normalize_box(face.get("bounding_box"))
                if nb and nb["width"] < 0.35 and nb["height"] < 0.40:
                    boxes.append(nb)
        if not boxes:
            return None
        areas = [_box_area(b) for b in boxes]
        largest_idx = max(range(len(boxes)), key=lambda i: areas[i])
        return boxes[largest_idx]
