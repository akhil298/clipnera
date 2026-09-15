from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

LOG = logging.getLogger(__name__)


SUPPORTED_ASPECT_RATIOS = ("9:16", "1:1", "4:5", "16:9")
DEFAULT_OUTPUT_DIMENSIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}


@dataclass
class SceneContext:
    layout: str = "unknown"
    layout_confidence: float = 0.0
    scene_start: float = 0.0
    scene_end: float = 0.0
    subjects: list[dict[str, Any]] = field(default_factory=list)
    faces: list[dict[str, Any]] = field(default_factory=list)
    active_speaker: dict[str, Any] | None = None
    importance_map: Any | None = None
    content_category: str = "unknown"
    aspect_ratio: str = "9:16"
    source_width: int = 1920
    source_height: int = 1080


@dataclass
class CropResult:
    x: float = 0.5
    y: float = 0.5
    width: float = 1.0
    height: float = 1.0
    strategy: str = "safe_fallback"
    confidence: float = 0.0
    camera_motion: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class CropStrategy(ABC):
    @abstractmethod
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        raise NotImplementedError

    @abstractmethod
    def validate_crop(self, crop: CropResult) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate_camera_motion(
        self, current: CropResult, target: CropResult, scene: SceneContext
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


def _parse_aspect_ratio(aspect_ratio: str) -> tuple[float, float]:
    normalized = aspect_ratio.strip().replace(":", "/")
    try:
        width, height = (float(part) for part in normalized.split("/", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")
    return width, height


def _target_crop_size(source_width: int, source_height: int, aspect_ratio: str) -> tuple[int, int]:
    target_width_ratio, target_height_ratio = _parse_aspect_ratio(aspect_ratio)
    source_ratio = source_width / max(1, source_height)
    target_ratio = target_width_ratio / max(1e-6, target_height_ratio)
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = max(2, int(round(crop_height * target_ratio)))
    else:
        crop_width = source_width
        crop_height = max(2, int(round(crop_width / target_ratio)))
    if crop_width % 2:
        crop_width -= 1
    if crop_height % 2:
        crop_height -= 1
    return max(2, crop_width), max(2, crop_height)


def _normalize_box(box: dict[str, Any] | None) -> dict[str, float] | None:
    if not box or not isinstance(box, dict):
        return None
    try:
        x = float(box.get("x", 0.0))
        y = float(box.get("y", 0.0))
        w = float(box.get("width", 0.0))
        h = float(box.get("height", 0.0))
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        w = min(1.0 - x, max(0.0, w))
        h = min(1.0 - y, max(0.0, h))
        return {"x": round(x, 6), "y": round(y, 6), "width": round(w, 6), "height": round(h, 6)}
    except (TypeError, ValueError):
        return None


def _box_area(box: dict[str, float]) -> float:
    return max(1e-6, box["width"]) * max(1e-6, box["height"])


class SafeFallbackStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        return {"fallback_reason": "unknown_or_low_confidence_layout"}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        return {"x": 0.5, "y": 0.5, "width": 1.0, "height": 1.0}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        cx = max(0.0, min(1.0, float(target.get("x", 0.5))))
        cy = max(0.0, min(1.0, float(target.get("y", 0.5))))
        crop_x = cx * scene.source_width - crop_w / 2
        crop_y = cy * scene.source_height - crop_h / 2
        crop_x = max(0.0, min(float(scene.source_width - crop_w), crop_x))
        crop_y = max(0.0, min(float(scene.source_height - crop_h), crop_y))
        return CropResult(
            x=round(crop_x / scene.source_width, 6),
            y=round(crop_y / scene.source_height, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="safe_fallback",
            confidence=0.0,
            notes=["centered_crop_fallback"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [{"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height}]


class SingleSubjectStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        primary = scene.active_speaker or (scene.faces[0] if scene.faces else None)
        if not primary and scene.subjects:
            areas = [_box_area(_normalize_box(s.get("bounding_box")) or {"x": 0, "y": 0, "width": 0, "height": 0}) for s in scene.subjects]
            if areas:
                primary = scene.subjects[max(range(len(areas)), key=lambda i: areas[i])]
        return {"primary_subject": primary}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        primary = analysis.get("primary_subject")
        if primary:
            nb = _normalize_box(primary.get("bounding_box"))
            if nb:
                return {"x": nb["x"] + nb["width"] / 2, "y": nb["y"] + nb["height"] / 2, "width": nb["width"], "height": nb["height"]}
        return {"x": 0.5, "y": 0.5, "width": 0.5, "height": 0.5}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        cx = max(0.0, min(1.0, float(target.get("x", 0.5))))
        cy = max(0.0, min(1.0, float(target.get("y", 0.5))))
        crop_x = cx * scene.source_width - crop_w / 2
        crop_y = cy * scene.source_height - crop_h / 2
        crop_x = max(0.0, min(float(scene.source_width - crop_w), crop_x))
        crop_y = max(0.0, min(float(scene.source_height - crop_h), crop_y))
        return CropResult(
            x=round(crop_x / scene.source_width, 6),
            y=round(crop_y / scene.source_height, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="single_subject",
            confidence=scene.layout_confidence,
            notes=[f"layout={scene.layout}"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [
            {"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height},
        ]


class TopBottomSpeakerStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        all_boxes = []
        for subj in (scene.subjects or []) + (scene.faces or []):
            nb = _normalize_box(subj.get("bounding_box"))
            if nb:
                all_boxes.append(nb)
        if len(all_boxes) < 2:
            return {"top_region": None, "bottom_region": None}
        top_box = min(all_boxes, key=lambda b: b["y"] + b["height"] / 2)
        bottom_box = max(all_boxes, key=lambda b: b["y"] + b["height"] / 2)
        return {"top_region": top_box, "bottom_region": bottom_box}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        top = analysis.get("top_region")
        bottom = analysis.get("bottom_region")
        active = _normalize_box(scene.active_speaker.get("bounding_box")) if scene.active_speaker else None
        if active:
            if top and abs(active["y"] - top["y"]) < abs(active["y"] - (bottom["y"] if bottom else 1.0)):
                return {"region": top, "zone": "top"}
            if bottom:
                return {"region": bottom, "zone": "bottom"}
        if top and bottom:
            return {"region": top, "zone": "top"}
        return {"x": 0.5, "y": 0.5, "width": 1.0, "height": 1.0}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        region = target.get("region", {})
        zone = target.get("zone", "center")
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        cx = region.get("x", 0.5) + region.get("width", 0.5) / 2
        cy = region.get("y", 0.5) + region.get("height", 0.5) / 2
        if zone == "top":
            cy = max(0.0, cy - crop_h / scene.source_height * 0.2)
        elif zone == "bottom":
            cy = min(1.0 - crop_h / scene.source_height, cy + crop_h / scene.source_height * 0.2)
        cx = max(0.0, min(1.0 - crop_w / scene.source_width, cx))
        cy = max(0.0, min(1.0 - crop_h / scene.source_height, cy))
        crop_x = cx * scene.source_width
        crop_y = cy * scene.source_height
        return CropResult(
            x=round(crop_x / scene.source_width, 6),
            y=round(crop_y / scene.source_height, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="top_bottom_speaker",
            confidence=scene.layout_confidence,
            notes=[f"zone={zone}", f"layout={scene.layout}"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [
            {"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height},
        ]


class LeftRightSpeakerStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        all_boxes = []
        for subj in (scene.subjects or []) + (scene.faces or []):
            nb = _normalize_box(subj.get("bounding_box"))
            if nb:
                all_boxes.append(nb)
        if len(all_boxes) < 2:
            return {"left_region": None, "right_region": None}
        left_box = min(all_boxes, key=lambda b: b["x"] + b["width"] / 2)
        right_box = max(all_boxes, key=lambda b: b["x"] + b["width"] / 2)
        return {"left_region": left_box, "right_region": right_box}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        left = analysis.get("left_region")
        right = analysis.get("right_region")
        active = _normalize_box(scene.active_speaker.get("bounding_box")) if scene.active_speaker else None
        if active:
            if left and abs(active["x"] - left["x"]) < abs(active["x"] - (right["x"] if right else 1.0)):
                return {"region": left, "zone": "left"}
            if right:
                return {"region": right, "zone": "right"}
        if left and right:
            return {"region": left, "zone": "left"}
        return {"x": 0.5, "y": 0.5, "width": 1.0, "height": 1.0}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        region = target.get("region", {})
        zone = target.get("zone", "center")
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        cx = region.get("x", 0.5) + region.get("width", 0.5) / 2
        cy = region.get("y", 0.5) + region.get("height", 0.5) / 2
        if zone == "left":
            cx = max(0.0, cx - crop_w / scene.source_width * 0.2)
        elif zone == "right":
            cx = min(1.0 - crop_w / scene.source_width, cx + crop_w / scene.source_width * 0.2)
        cx = max(0.0, min(1.0 - crop_w / scene.source_width, cx))
        cy = max(0.0, min(1.0 - crop_h / scene.source_height, cy))
        return CropResult(
            x=round(cx, 6),
            y=round(cy, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="left_right_speaker",
            confidence=scene.layout_confidence,
            notes=[f"zone={zone}", f"layout={scene.layout}"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [
            {"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height},
        ]


class GamingStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        game_boxes = []
        face_boxes = []
        for frame in scene.frames or []:
            for subj in (frame.get("subjects", []) or []) + (frame.get("faces", []) or []):
                nb = _normalize_box(subj.get("bounding_box"))
                if nb:
                    area = _box_area(nb)
                    if area < 0.25:
                        face_boxes.append(nb)
                    else:
                        game_boxes.append(nb)
        return {"game_regions": game_boxes, "face_regions": face_boxes}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        game_boxes = analysis.get("game_regions", [])
        face_boxes = analysis.get("face_regions", [])
        if game_boxes and face_boxes:
            best_face = max(face_boxes, key=_box_area)
            best_game = max(game_boxes, key=_box_area)
            return {"game": best_game, "face": best_face}
        if game_boxes:
            best_game = max(game_boxes, key=_box_area)
            return {"game": best_game}
        return {"x": 0.5, "y": 0.5, "width": 1.0, "height": 1.0}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        game = target.get("game")
        face = target.get("face")
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        if game and face:
            gcx = game["x"] + game["width"] / 2
            gcy = game["y"] + game["height"] / 2
            fcx = face["x"] + face["width"] / 2
            fcy = face["y"] + face["height"] / 2
            cx = gcx * 0.65 + fcx * 0.35
            cy = gcy * 0.65 + fcy * 0.35
        elif game:
            cx = game["x"] + game["width"] / 2
            cy = game["y"] + game["height"] / 2
        else:
            cx, cy = 0.5, 0.5
        cx = max(0.0, min(1.0 - crop_w / scene.source_width, cx))
        cy = max(0.0, min(1.0 - crop_h / scene.source_height, cy))
        return CropResult(
            x=round(cx, 6),
            y=round(cy, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="gaming",
            confidence=scene.layout_confidence,
            notes=["balanced_gameplay_facecam"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [
            {"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height},
        ]


class ScreenShareStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        return {"preserve_region": "screen"}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        im = scene.importance_map
        if im and im.regions:
            screen = next((r for r in im.regions if r.region_type == "screen"), None)
            if screen:
                return {"x": screen.x, "y": screen.y, "width": screen.width, "height": screen.height}
        return {"x": 0.5, "y": 0.5, "width": 1.0, "height": 1.0}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        cx = max(0.0, min(1.0 - crop_w / scene.source_width, float(target.get("x", 0.5))))
        cy = max(0.0, min(1.0 - crop_h / scene.source_height, float(target.get("y", 0.5))))
        return CropResult(
            x=round(cx, 6),
            y=round(cy, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="screen_share",
            confidence=scene.layout_confidence,
            notes=["preserve_screen_region"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [
            {"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height},
        ]


class MultiSubjectStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        all_boxes = []
        for subj in (scene.subjects or []) + (scene.faces or []):
            nb = _normalize_box(subj.get("bounding_box"))
            if nb:
                all_boxes.append(nb)
        if not all_boxes:
            return {"regions": []}
        xs = [b["x"] + b["width"] / 2 for b in all_boxes]
        ys = [b["y"] + b["height"] / 2 for b in all_boxes]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        width = max(b["x"] + b["width"] for b in all_boxes) - min(b["x"] for b in all_boxes)
        height = max(b["y"] + b["height"] for b in all_boxes) - min(b["y"] for b in all_boxes)
        return {
            "regions": all_boxes,
            "center": {"x": max(0.0, min(1.0, cx)), "y": max(0.0, min(1.0, cy))},
            "span_width": max(0.0, min(1.0, width)),
            "span_height": max(0.0, min(1.0, height)),
        }

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        return analysis.get("center", {"x": 0.5, "y": 0.5})

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        crop_w, crop_h = _target_crop_size(scene.source_width, scene.source_height, scene.aspect_ratio)
        cx = max(0.0, min(1.0 - crop_w / scene.source_width, float(target.get("x", 0.5))))
        cy = max(0.0, min(1.0 - crop_h / scene.source_height, float(target.get("y", 0.5))))
        return CropResult(
            x=round(cx, 6),
            y=round(cy, 6),
            width=round(crop_w / scene.source_width, 6),
            height=round(crop_h / scene.source_height, 6),
            strategy="multi_subject",
            confidence=scene.layout_confidence,
            notes=[f"layout={scene.layout}"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return 0.0 <= crop.x <= 1.0 and 0.0 <= crop.y <= 1.0 and 0.0 < crop.width <= 1.0 and 0.0 < crop.height <= 1.0

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [
            {"timestamp": scene.scene_start, "x": target.x, "y": target.y, "width": target.width, "height": target.height},
        ]


class NoChangeStrategy(CropStrategy):
    def analyze(self, scene: SceneContext) -> dict[str, Any]:
        return {"noop": True}

    def select_target(self, scene: SceneContext, analysis: dict[str, Any]) -> dict[str, Any]:
        return {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}

    def calculate_crop(self, scene: SceneContext, target: dict[str, Any]) -> CropResult:
        return CropResult(
            x=0.0, y=0.0, width=1.0, height=1.0,
            strategy="no_change", confidence=1.0, notes=["no_crop_change"],
        )

    def validate_crop(self, crop: CropResult) -> bool:
        return True

    def generate_camera_motion(self, current: CropResult, target: CropResult, scene: SceneContext) -> list[dict[str, Any]]:
        return [{"timestamp": scene.scene_start, "x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}]


STRATEGY_REGISTRY: dict[str, type[CropStrategy]] = {
    "safe_fallback": SafeFallbackStrategy,
    "single_subject": SingleSubjectStrategy,
    "top_bottom_speaker": TopBottomSpeakerStrategy,
    "left_right_speaker": LeftRightSpeakerStrategy,
    "gaming": GamingStrategy,
    "screen_share": ScreenShareStrategy,
    "multi_subject": MultiSubjectStrategy,
    "no_change": NoChangeStrategy,
}

LAYOUT_TO_STRATEGY: dict[str, str] = {
    "single_subject": "single_subject",
    "two_subjects_top_bottom": "top_bottom_speaker",
    "two_subjects_left_right": "left_right_speaker",
    "multi_subject_grid": "multi_subject",
    "stacked_multi_subject": "multi_subject",
    "gaming_with_facecam": "gaming",
    "gameplay_only": "gaming",
    "speaker_plus_screen": "screen_share",
    "podcast_interview": "top_bottom_speaker",
    "screen_share": "screen_share",
    "presentation": "screen_share",
    "reaction_video": "single_subject",
    "mixed_layout": "multi_subject",
    "unknown": "safe_fallback",
}


class CropStrategySelector:
    def __init__(self) -> None:
        self._registry = dict(STRATEGY_REGISTRY)
        self._layout_map = dict(LAYOUT_TO_STRATEGY)

    def register_strategy(self, name: str, strategy_cls: type[CropStrategy]) -> None:
        self._registry[name] = strategy_cls
        LOG.debug("Registered crop strategy: %s", name)

    def register_layout_mapping(self, layout: str, strategy_name: str) -> None:
        self._layout_map[layout] = strategy_name
        LOG.debug("Registered layout->strategy mapping: %s -> %s", layout, strategy_name)

    def select(self, scene: SceneContext) -> tuple[CropStrategy, CropResult]:
        strategy_name = self._layout_map.get(scene.layout, "safe_fallback")
        if scene.layout_confidence < 0.25:
            strategy_name = "safe_fallback"
        if scene.aspect_ratio == "16:9":
            strategy_name = "no_change"
        strategy_cls = self._registry.get(strategy_name, SafeFallbackStrategy)
        strategy = strategy_cls()
        analysis = strategy.analyze(scene)
        target = strategy.select_target(scene, analysis)
        crop = strategy.calculate_crop(scene, target)
        if not strategy.validate_crop(crop):
            LOG.debug("Crop validation failed for %s, falling back to safe", strategy_name)
            fallback = SafeFallbackStrategy()
            analysis = fallback.analyze(scene)
            target = fallback.select_target(scene, analysis)
            crop = fallback.calculate_crop(scene, target)
        motion = strategy.generate_camera_motion(
            CropResult(x=0.5, y=0.5, width=1.0, height=1.0),
            crop, scene,
        )
        crop.camera_motion = motion
        LOG.debug(
            "Strategy selected: %s (layout=%s, confidence=%.3f)",
            strategy_name, scene.layout, scene.layout_confidence,
            extra={
                "strategy": strategy_name,
                "layout": scene.layout,
                "layout_confidence": scene.layout_confidence,
                "aspect_ratio": scene.aspect_ratio,
                "content_category": scene.content_category,
            },
        )
        return strategy, crop


def build_crop_tracking(
    scene: SceneContext,
    fps: float = 2.0,
) -> list[dict[str, Any]]:
    selector = CropStrategySelector()
    _, crop = selector.select(scene)
    duration = max(0.0, scene.scene_end - scene.scene_start)
    if duration <= 0.0:
        duration = 5.0
    n_points = max(2, int(duration * fps))
    step = duration / max(1, n_points - 1)
    tracking: list[dict[str, Any]] = []
    for i in range(n_points):
        ts = round(scene.scene_start + i * step, 3)
        tracking.append({
            "timestamp": ts,
            "bbox": {
                "x": round(crop.x, 6),
                "y": round(crop.y, 6),
                "width": round(crop.width, 6),
                "height": round(crop.height, 6),
            },
            "strategy": crop.strategy,
            "confidence": crop.confidence,
        })
    return tracking
