from __future__ import annotations

import asyncio
import math
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

SUPPORTED_ASPECT_RATIOS = ("9:16", "1:1", "4:5", "16:9")
DEFAULT_OUTPUT_DIMENSIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}
MAX_TRACKING_POINTS = 100
MAX_TOTAL_TRACKING_POINTS = 120


def parse_aspect_ratio(aspect_ratio: str) -> tuple[float, float]:
    normalized = aspect_ratio.strip().replace(":", "/")
    try:
        width, height = (float(part) for part in normalized.split("/", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")
    return width, height


def normalize_box(box: dict[str, Any], frame_width: int | None = None, frame_height: int | None = None) -> dict[str, float]:
    x = float(box.get("x", 0.0))
    y = float(box.get("y", 0.0))
    width = float(box.get("width", 0.0))
    height = float(box.get("height", 0.0))

    if frame_width and max(x, width) > 1.0:
        x /= frame_width
        width /= frame_width
    if frame_height and max(y, height) > 1.0:
        y /= frame_height
        height /= frame_height

    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    width = min(1.0 - x, max(0.0, width))
    height = min(1.0 - y, max(0.0, height))
    return {"x": round(x, 6), "y": round(y, 6), "width": round(width, 6), "height": round(height, 6)}


def crop_tracking_expressions(
    crop_tracking: list[dict[str, Any]],
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
) -> tuple[str, str]:
    if not crop_tracking:
        return str((source_width - crop_width) // 2), str((source_height - crop_height) // 2)

    points = [(float(item.get("timestamp", 0.0)), item.get("bbox", {})) for item in crop_tracking]
    points = [(timestamp, normalize_box(box)) for timestamp, box in points if box]
    if not points:
        return str((source_width - crop_width) // 2), str((source_height - crop_height) // 2)
    points.sort(key=lambda item: item[0])
    if len(points) == 1:
        timestamp, box = points[0]
        return (
            f"clip({box['x'] * source_width:.6f},0,{max(0, source_width - crop_width)})",
            f"clip({box['y'] * source_height:.6f},0,{max(0, source_height - crop_height)})",
        )

    def axis_expression(axis: str) -> str:
        segments = []
        for (start_time, start_box), (end_time, end_box) in zip(points, points[1:]):
            start_value = start_box[axis] * (source_width if axis == "x" else source_height)
            end_value = end_box[axis] * (source_width if axis == "x" else source_height)
            duration = max(end_time - start_time, 1e-6)
            limit = max(0, (source_width if axis == "x" else source_height) - (crop_width if axis == "x" else crop_height))
            expression = f"clip({start_value:.6f}+({end_value:.6f}-{start_value:.6f})*(t-{start_time:.6f})/{duration:.6f},0,{limit})"
            segments.append((end_time, expression))
        _, last_box = points[-1]
        last_value = last_box[axis] * (source_width if axis == "x" else source_height)
        limit = max(0, (source_width if axis == "x" else source_height) - (crop_width if axis == "x" else crop_height))
        expression = f"clip({last_value:.6f},0,{limit})"
        for timestamp, segment in reversed(segments):
            expression = f"if(lt(t,{timestamp:.6f}),{segment},{expression})"
        return expression

    return axis_expression("x"), axis_expression("y")


def output_dimensions(aspect_ratio: str, preferred: tuple[int, int] | None = None) -> tuple[int, int]:
    if preferred:
        width, height = preferred
        target_width, target_height = parse_aspect_ratio(aspect_ratio)
        if not math.isclose(width / height, target_width / target_height, rel_tol=1e-6):
            raise ValueError(f"Preferred dimensions do not match {aspect_ratio}")
        return width, height
    return DEFAULT_OUTPUT_DIMENSIONS[aspect_ratio]


def _normalize_box_for_importance(box: dict[str, Any] | None) -> dict[str, float] | None:
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


def _ensure_analyzers():
    from content_intelligence.layout_analyzer import LayoutAnalyzer
    from content_intelligence.content_importance import ContentImportanceAnalyzer
    from content_intelligence.crop_strategy import CropStrategySelector, SceneContext
    return LayoutAnalyzer, ContentImportanceAnalyzer, CropStrategySelector, SceneContext


async def _extract_opencv_frames(video_path: str, duration: float):
    try:
        from content_intelligence.opencv_analyzer import OpenCVAnalyzer
        analyzer = OpenCVAnalyzer()
        if duration <= 0:
            return None
        interval = analyzer._frame_interval or max(2.0, duration / analyzer._max_frames)
        timestamps = [i * interval for i in range(analyzer._max_frames) if i * interval < duration]
        return await asyncio.to_thread(analyzer._extract_frames_sync, video_path, timestamps)
    except Exception as exc:
        log.warning("OpenCV frame extraction failed: %s", exc)
        return None


def _opencv_scene_fallback(frames: list[Any]) -> list[float]:
    try:
        from content_intelligence.opencv_analyzer import OpenCVAnalyzer
        return OpenCVAnalyzer().detect_scenes(frames)
    except Exception as exc:
        log.warning("OpenCV scene detection failed: %s", exc)
        return []


def _opencv_frame_supplement(frame_analyses: list[dict[str, Any]], frames: list[Any]) -> list[dict[str, Any]]:
    try:
        from content_intelligence.opencv_analyzer import OpenCVAnalyzer
        analyzer = OpenCVAnalyzer()
        motion_map = analyzer.compute_motion_map(frames)
        saliency_map = {}
        for opencv_frame in frames:
            saliency = analyzer.compute_saliency(opencv_frame)
            if saliency:
                saliency_map[opencv_frame.timestamp] = saliency
        augmented = list(frame_analyses)
        for frame in augmented:
            timestamp = float(frame.get("timestamp", 0.0))
            if timestamp in motion_map:
                frame["opencv_motion"] = motion_map[timestamp]
            if timestamp in saliency_map:
                frame["opencv_saliency"] = saliency_map[timestamp]
        return augmented
    except Exception as exc:
        log.warning("OpenCV frame supplement failed: %s", exc)
        return frame_analyses


async def build_smart_output_formats(
    frame_analyses: list[dict[str, Any]],
    source_width: int,
    source_height: int,
    aspect_ratios: list[str] | None = None,
    content_category: str = "unknown",
    transcript_segments: list[dict[str, Any]] | None = None,
    scene_changes: list[float] | None = None,
    video_path: str | None = None,
    margin: float = 0.08,
) -> dict[str, dict[str, Any]]:
    ratios = [r for r in (aspect_ratios or list(SUPPORTED_ASPECT_RATIOS)) if r in SUPPORTED_ASPECT_RATIOS]
    if not ratios:
        ratios = list(SUPPORTED_ASPECT_RATIOS)

    LayoutAnalyzer, ContentImportanceAnalyzer, CropStrategySelector, SceneContext = _ensure_analyzers()

    frames = list(frame_analyses)
    if video_path and frames:
        try:
            duration = max(0.0, max(float(f.get("timestamp", 0.0)) for f in frames) + 5.0)
            opencv_frames = await _extract_opencv_frames(video_path, duration)
            if opencv_frames:
                log.info("OpenCV preprocessing frames extracted: %d", len(opencv_frames))
                if not scene_changes:
                    scene_changes = _opencv_scene_fallback(opencv_frames)
                frames = _opencv_frame_supplement(frames, opencv_frames)
        except Exception as exc:
            log.warning("OpenCV preprocessing failed: %s", exc)

    if not frames:
        log.warning("No frame analyses available for smart output, cannot proceed without OpenCV data")
        raise ValueError("No frame analyses available for smart output")

    layout_analyzer = LayoutAnalyzer()
    importance_analyzer = ContentImportanceAnalyzer()
    strategy_selector = CropStrategySelector()

    layout_decisions = layout_analyzer.analyze_scenes(
        frames=frames,
        scene_changes=scene_changes,
        content_category=content_category,
    )
    log.info(
        "Layout analysis complete",
        extra={
            "content_category": content_category,
            "scene_count": len(layout_decisions),
            "layouts": [d.layout for d in layout_decisions],
            "confidences": [round(d.confidence, 3) for d in layout_decisions],
        },
    )

    outputs: dict[str, dict[str, Any]] = {}
    for aspect_ratio in ratios:
        target_width, target_height = DEFAULT_OUTPUT_DIMENSIONS[aspect_ratio]
        tracking: list[dict[str, Any]] = []
        for layout_decision in layout_decisions:
            scene_frames = [
                f for f in frames
                if layout_decision.scene_start <= float(f.get("timestamp", 0.0)) < layout_decision.scene_end
            ]
            if not scene_frames:
                scene_frames = frames[:3]
            scene_dict: dict[str, Any] = {
                "scene_start": layout_decision.scene_start,
                "scene_end": layout_decision.scene_end,
                "frames": scene_frames,
            }
            importance_map = importance_analyzer.analyze(scene_dict, content_category=content_category)
            active_speaker = importance_analyzer._find_active_speaker(scene_frames)
            all_faces: list[dict[str, Any]] = []
            for f in scene_frames:
                for face in f.get("faces", []) or []:
                    nb = _normalize_box_for_importance(face.get("bounding_box"))
                    if nb:
                        all_faces.append(face)
            ctx = SceneContext(
                layout=layout_decision.layout,
                layout_confidence=layout_decision.confidence,
                scene_start=layout_decision.scene_start,
                scene_end=layout_decision.scene_end,
                subjects=[
                    s for f in scene_frames for s in (f.get("subjects", []) or [])
                ],
                faces=all_faces,
                active_speaker=active_speaker,
                importance_map=importance_map,
                content_category=content_category,
                aspect_ratio=aspect_ratio,
                source_width=source_width,
                source_height=source_height,
            )
            _, crop_result = CropStrategySelector().select(ctx)
            fps = max(1.0, len(scene_frames) / max(1.0, layout_decision.scene_end - layout_decision.scene_start))
            scene_tracking = _build_crop_tracking(ctx, fps=fps)
            tracking.extend(scene_tracking)
            log.info(
                "Crop strategy applied",
                extra={
                    "aspect_ratio": aspect_ratio,
                    "layout": layout_decision.layout,
                    "strategy": crop_result.strategy,
                    "confidence": crop_result.confidence,
                    "crop_x": crop_result.x,
                    "crop_y": crop_result.y,
                    "crop_w": crop_result.width,
                    "crop_h": crop_result.height,
                    "scene_start": layout_decision.scene_start,
                    "scene_end": layout_decision.scene_end,
                },
            )

        if not tracking and frames:
            tracking = _build_crop_tracking(
                SceneContext(
                    layout="unknown",
                    layout_confidence=0.0,
                    scene_start=0.0,
                    scene_end=frames[-1].get("timestamp", 0.0) + 5.0,
                    source_width=source_width,
                    source_height=source_height,
                    aspect_ratio=aspect_ratio,
                    content_category=content_category,
                ),
                fps=2.0,
            )
        tracking = _subsample_tracking(tracking, MAX_TOTAL_TRACKING_POINTS)
        tracking = _smooth_tracking(tracking)
        initial_crop = tracking[0]["bbox"] if tracking else {
            "x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0,
        }
        tracking_enabled = aspect_ratio != "16:9" and len(tracking) > 1
        outputs[aspect_ratio] = {
            "crop": initial_crop,
            "tracking": tracking_enabled,
            "crop_tracking": tracking,
            "target_width": target_width,
            "target_height": target_height,
        }
    return outputs


def _subsample_tracking(tracking: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(tracking) <= limit:
        return tracking
    step = max(1, len(tracking) / limit)
    indices = [int(round(i * step)) for i in range(limit)]
    indices = [min(i, len(tracking) - 1) for i in indices]
    seen: set[int] = set()
    subsampled: list[dict[str, Any]] = []
    for i in indices:
        if i not in seen:
            seen.add(i)
            subsampled.append(tracking[i])
    if subsampled[-1] is not tracking[-1]:
        subsampled.append(tracking[-1])
    return subsampled


def _smooth_tracking(tracking: list[dict[str, Any]], max_jump: float = 0.08) -> list[dict[str, Any]]:
    if len(tracking) < 3:
        return tracking
    smoothed = [dict(tracking[0])]
    for i in range(1, len(tracking)):
        prev = smoothed[-1].get("bbox", {})
        curr = tracking[i].get("bbox", {})
        next_box = {
            "x": max(0.0, min(1.0, curr.get("x", prev.get("x", 0.5)))),
            "y": max(0.0, min(1.0, curr.get("y", prev.get("y", 0.5)))),
            "width": max(0.05, min(1.0, curr.get("width", prev.get("width", 1.0)))),
            "height": max(0.05, min(1.0, curr.get("height", prev.get("height", 1.0)))),
        }
        dx = max(0.0, abs(next_box["x"] - prev["x"]) - max_jump)
        dy = max(0.0, abs(next_box["y"] - prev["y"]) - max_jump)
        dw = max(0.0, abs(next_box["width"] - prev["width"]) - max_jump)
        dh = max(0.0, abs(next_box["height"] - prev["height"]) - max_jump)
        if dx > 0 or dy > 0 or dw > 0 or dh > 0:
            factor = 0.35
            next_box = {
                "x": prev["x"] + (next_box["x"] - prev["x"]) * factor,
                "y": prev["y"] + (next_box["y"] - prev["y"]) * factor,
                "width": prev["width"] + (next_box["width"] - prev["width"]) * factor,
                "height": prev["height"] + (next_box["height"] - prev["height"]) * factor,
            }
        smoothed.append({**tracking[i], "bbox": next_box})
    return smoothed


def _build_crop_tracking(scene: SceneContext, fps: float = 2.0) -> list[dict[str, Any]]:
    from content_intelligence.crop_strategy import CropStrategySelector
    selector = CropStrategySelector()
    _, crop = selector.select(scene)
    duration = max(0.0, scene.scene_end - scene.scene_start)
    if duration <= 0.0:
        duration = 5.0
    n_points = max(2, int(duration * fps))
    if n_points > MAX_TRACKING_POINTS:
        fps = MAX_TRACKING_POINTS / duration
        n_points = MAX_TRACKING_POINTS
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
