from __future__ import annotations

import math
from typing import Any, Iterable

SUPPORTED_ASPECT_RATIOS = ("9:16", "1:1", "4:5", "16:9")
DEFAULT_OUTPUT_DIMENSIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}


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



def _subjects(frame: dict[str, Any]) -> list[dict[str, Any]]:
    subjects = frame.get("subjects") or frame.get("objects") or []
    return [s for s in subjects if s.get("bounding_box")]


def _subject_score(subject: dict[str, Any]) -> float:
    label = str(subject.get("label", "")).lower()
    confidence = min(1.0, max(0.0, float(subject.get("confidence", 0.0) or 0.0)))
    box = normalize_box(subject.get("bounding_box", {}))
    area = max(box["width"] * box["height"], 1e-6)
    speaker_bonus = 0.35 if subject.get("is_speaker") or subject.get("speaker") else 0.0
    person_bonus = 0.2 if any(token in label for token in ("person", "speaker", "prime minister", "interviewer", "guest")) else 0.0
    return confidence * (0.5 + area) + speaker_bonus + person_bonus


def primary_subject(frame: dict[str, Any]) -> dict[str, Any] | None:
    subjects = _subjects(frame)
    return max(subjects, key=_subject_score) if subjects else None


def _target_crop_size(source_width: int, source_height: int, aspect_ratio: str) -> tuple[int, int]:
    target_width_ratio, target_height_ratio = parse_aspect_ratio(aspect_ratio)
    source_ratio = source_width / source_height
    target_ratio = target_width_ratio / target_height_ratio
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = max(1, int(round(crop_height * target_ratio)))
    else:
        crop_width = source_width
        crop_height = max(1, int(round(crop_width / target_ratio)))
    if crop_width % 2:
        crop_width -= 1
    if crop_height % 2:
        crop_height -= 1
    return max(2, crop_width), max(2, crop_height)


def _expanded_subject_box(subject: dict[str, Any], margin: float) -> dict[str, float]:
    box = normalize_box(subject.get("bounding_box", {}))
    padding = max(0.0, margin)
    x = max(0.0, box["x"] - padding)
    y = max(0.0, box["y"] - padding)
    right = min(1.0, box["x"] + box["width"] + padding)
    bottom = min(1.0, box["y"] + box["height"] + padding)
    return {"x": x, "y": y, "width": right - x, "height": bottom - y}


def crop_for_subject(
    frame: dict[str, Any],
    source_width: int,
    source_height: int,
    aspect_ratio: str,
    margin: float = 0.08,
) -> dict[str, float]:
    crop_width, crop_height = _target_crop_size(source_width, source_height, aspect_ratio)
    subject = primary_subject(frame)
    if not subject:
        return {
            "x": round((source_width - crop_width) / 2 / source_width, 6),
            "y": round((source_height - crop_height) / 2 / source_height, 6),
            "width": round(crop_width / source_width, 6),
            "height": round(crop_height / source_height, 6),
        }

    subject_box = _expanded_subject_box(subject, margin)
    center_x = subject_box["x"] + subject_box["width"] / 2
    center_y = subject_box["y"] + subject_box["height"] / 2
    crop_x = center_x * source_width - crop_width / 2
    crop_y = center_y * source_height - crop_height / 2
    crop_x = min(source_width - crop_width, max(0.0, crop_x))
    crop_y = min(source_height - crop_height, max(0.0, crop_y))
    return {
        "x": round(crop_x / source_width, 6),
        "y": round(crop_y / source_height, 6),
        "width": round(crop_width / source_width, 6),
        "height": round(crop_height / source_height, 6),
    }


def build_crop_tracking(
    frame_analyses: Iterable[dict[str, Any]],
    source_width: int,
    source_height: int,
    aspect_ratio: str,
    margin: float = 0.08,
) -> list[dict[str, Any]]:
    tracking: list[dict[str, Any]] = []
    for frame in frame_analyses:
        timestamp = float(frame.get("timestamp", 0.0))
        tracking.append({
            "timestamp": round(timestamp, 3),
            "bbox": crop_for_subject(frame, source_width, source_height, aspect_ratio, margin),
        })
    return tracking


def build_output_formats(
    frame_analyses: Iterable[dict[str, Any]],
    source_width: int,
    source_height: int,
    aspect_ratios: Iterable[str] = SUPPORTED_ASPECT_RATIOS,
    margin: float = 0.08,
) -> dict[str, dict[str, Any]]:
    frames = list(frame_analyses)
    outputs: dict[str, dict[str, Any]] = {}
    for aspect_ratio in aspect_ratios:
        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")
        if frames and all("bbox" in item and "timestamp" in item for item in frames):
            tracking = [
                {"timestamp": float(item.get("timestamp", 0.0)), "bbox": normalize_box(item.get("bbox", {}))}
                for item in frames
            ]
            crop = tracking[0]["bbox"] if tracking else {
                "x": 0.0,
                "y": 0.0,
                "width": 1.0,
                "height": 1.0,
            }
        else:
            tracking = build_crop_tracking(frames, source_width, source_height, aspect_ratio, margin)
            crop = tracking[0]["bbox"] if tracking else {
                "x": 0.0,
                "y": 0.0,
                "width": 1.0,
                "height": 1.0,
            }
        tracking_enabled = aspect_ratio != "16:9" and len(tracking) > 1
        outputs[aspect_ratio] = {
            "crop": crop,
            "tracking": tracking_enabled,
            "crop_tracking": tracking,
            "target_width": DEFAULT_OUTPUT_DIMENSIONS[aspect_ratio][0],
            "target_height": DEFAULT_OUTPUT_DIMENSIONS[aspect_ratio][1],
        }
    return outputs


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
