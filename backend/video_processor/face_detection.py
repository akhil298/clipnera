"""Face detection for reframing, CPU-only and dependency-light.

Two backends, chosen at runtime:

* **YuNet** (``cv2.FaceDetectorYN``) when an ONNX model is available. More
  accurate, handles profile and angled faces, ~340KB, still fast on CPU.
* **Haar cascades** otherwise. These ship inside the ``opencv-contrib-python``
  wheel, so this backend needs no downloads and works on a bare EC2 instance.

Nothing here calls a network service, which keeps reframing free and keeps the
pipeline working when an instance has no outbound internet access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.logging_config import get_logger
from video_processor.geometry import Box, normalize_box

log = get_logger(__name__)

# Where to look for the optional YuNet model, in priority order. Drop
# face_detection_yunet_2023mar.onnx in backend/models/ to enable it.
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
YUNET_SEARCH_PATHS = (
    Path(__file__).resolve().parent.parent / "models" / YUNET_FILENAME,
    Path("/opt/clipnera/models") / YUNET_FILENAME,
)

MIN_FACE_CONFIDENCE = 0.6
# Faces smaller than this fraction of frame width are usually background
# bystanders or detector noise, not the subject we should be framing on.
MIN_FACE_WIDTH_RATIO = 0.02
# Detections overlapping more than this are treated as the same face.
DEDUPE_IOU = 0.4


@dataclass(frozen=True)
class Face:
    """A detected face in normalised, top-left-origin coordinates."""

    box: Box
    confidence: float
    # Mouth region, derived from landmarks when available and from face
    # proportions otherwise. Used for active-speaker lip motion.
    mouth: Box

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": "face",
            "confidence": round(self.confidence, 4),
            "bounding_box": self.box.as_dict(),
            "mouth_box": self.mouth.as_dict(),
        }


def _mouth_from_box(face: Box) -> Box:
    """Approximate the mouth region from face proportions.

    The mouth sits in the lower third of a face box, horizontally centred and
    about half its width.
    """
    width = face.width * 0.5
    height = face.height * 0.25
    x = face.x + (face.width - width) / 2
    y = face.y + face.height * 0.62
    return Box(
        x=max(0.0, x),
        y=max(0.0, min(1.0 - height, y)),
        width=max(1e-6, width),
        height=max(1e-6, height),
    )


def _mouth_from_landmarks(face: Box, left: tuple[float, float], right: tuple[float, float]) -> Box:
    """Mouth region spanning YuNet's two mouth-corner landmarks."""
    x0, x1 = sorted((left[0], right[0]))
    y0, y1 = sorted((left[1], right[1]))
    pad_x = max(0.01, (x1 - x0) * 0.35)
    pad_y = max(0.012, face.height * 0.10)
    x = max(0.0, x0 - pad_x)
    y = max(0.0, y0 - pad_y)
    width = min(1.0 - x, (x1 - x0) + pad_x * 2)
    height = min(1.0 - y, (y1 - y0) + pad_y * 2)
    if width <= 0 or height <= 0:
        return _mouth_from_box(face)
    return Box(x=x, y=y, width=width, height=height)


@lru_cache(maxsize=1)
def _yunet_model_path() -> str | None:
    override = os.getenv("YUNET_MODEL_PATH", "").strip()
    candidates = [Path(override)] if override else []
    candidates.extend(YUNET_SEARCH_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


class FaceDetector:
    """Detects faces in BGR frames, normalised to the frame size."""

    def __init__(self, min_confidence: float = MIN_FACE_CONFIDENCE) -> None:
        self._min_confidence = min_confidence
        self._yunet: Any | None = None
        self._yunet_size: tuple[int, int] | None = None
        self._frontal: Any | None = None
        self._profile: Any | None = None
        self._backend = self._select_backend()

    @property
    def backend(self) -> str:
        return self._backend

    def _select_backend(self) -> str:
        model_path = _yunet_model_path()
        if model_path and hasattr(cv2, "FaceDetectorYN"):
            try:
                self._yunet = cv2.FaceDetectorYN.create(
                    model=model_path,
                    config="",
                    input_size=(320, 320),
                    score_threshold=self._min_confidence,
                )
                log.info("Face detection backend: YuNet (%s)", model_path)
                return "yunet"
            except cv2.error as exc:
                log.warning("YuNet unavailable, falling back to Haar cascades: %s", exc)

        cascade_dir = Path(cv2.data.haarcascades)
        self._frontal = cv2.CascadeClassifier(str(cascade_dir / "haarcascade_frontalface_default.xml"))
        self._profile = cv2.CascadeClassifier(str(cascade_dir / "haarcascade_profileface.xml"))
        if self._frontal.empty():
            log.error("Haar frontal-face cascade failed to load; face detection disabled")
            return "none"
        log.info(
            "Face detection backend: Haar cascades (bundled). Add %s to backend/models/ for better accuracy.",
            YUNET_FILENAME,
        )
        return "haar"

    def detect(self, frame: np.ndarray) -> list[Face]:
        if frame is None or getattr(frame, "size", 0) == 0:
            return []
        if self._backend == "yunet":
            faces = self._detect_yunet(frame)
        elif self._backend == "haar":
            faces = self._detect_haar(frame)
        else:
            return []
        return self._postprocess(faces)

    def _detect_yunet(self, frame: np.ndarray) -> list[Face]:
        height, width = frame.shape[:2]
        if self._yunet_size != (width, height):
            self._yunet.setInputSize((width, height))
            self._yunet_size = (width, height)
        try:
            _, detections = self._yunet.detect(frame)
        except cv2.error as exc:
            log.debug("YuNet detection failed: %s", exc)
            return []
        if detections is None:
            return []

        faces: list[Face] = []
        for row in detections:
            box = normalize_box(
                {"x": float(row[0]), "y": float(row[1]), "width": float(row[2]), "height": float(row[3])},
                frame_width=width,
                frame_height=height,
            )
            if box is None:
                continue
            confidence = float(row[14])
            # Landmarks 3 and 4 are the mouth corners.
            mouth_left = (float(row[10]) / width, float(row[11]) / height)
            mouth_right = (float(row[12]) / width, float(row[13]) / height)
            faces.append(Face(box=box, confidence=confidence, mouth=_mouth_from_landmarks(box, mouth_left, mouth_right)))
        return faces

    def _detect_haar(self, frame: np.ndarray) -> list[Face]:
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        min_size = max(24, int(width * MIN_FACE_WIDTH_RATIO))

        detections: list[tuple[int, int, int, int]] = []
        for cascade in (self._frontal, self._profile):
            if cascade is None or cascade.empty():
                continue
            found = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(min_size, min_size),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            detections.extend((int(x), int(y), int(w), int(h)) for x, y, w, h in found)

        faces: list[Face] = []
        for x, y, w, h in detections:
            box = normalize_box(
                {"x": x, "y": y, "width": w, "height": h},
                frame_width=width,
                frame_height=height,
            )
            if box is None:
                continue
            # Haar gives no score; size is the only available quality signal.
            faces.append(Face(box=box, confidence=0.75, mouth=_mouth_from_box(box)))
        return faces

    def _postprocess(self, faces: list[Face]) -> list[Face]:
        """Drop weak and tiny detections, then merge duplicates."""
        candidates = [
            face for face in faces
            if face.confidence >= self._min_confidence and face.box.width >= MIN_FACE_WIDTH_RATIO
        ]
        candidates.sort(key=lambda f: (f.confidence, f.box.area), reverse=True)

        kept: list[Face] = []
        for face in candidates:
            if any(face.box.intersection_over_union(k.box) > DEDUPE_IOU for k in kept):
                continue
            kept.append(face)
        return kept
