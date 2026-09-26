"""Face detection for reframing, CPU-only and dependency-light.

Three backends, the first available one wins:

* **RetinaFace-ResNet50** (ONNX, run by onnxruntime) when its model is present.
  The most accurate by a wide margin on small, angled and partly hidden faces;
  ~109MB and several times slower than YuNet, still CPU-only.
* **YuNet** (``cv2.FaceDetectorYN``) when its ONNX model is available. Handles
  profile and angled faces, ~340KB, fast on CPU.
* **Haar cascades** otherwise. These ship inside the ``opencv-contrib-python``
  wheel, so this backend needs no downloads and works on a bare EC2 instance.

With both RetinaFace and YuNet present, ``FaceDetector.detect_clip`` runs YuNet
on every frame and escalates a clip to RetinaFace only when spot checks show
YuNet missing faces there.

Nothing here calls a network service, which keeps reframing free and keeps the
pipeline working when an instance has no outbound internet access.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from collections.abc import Callable, Iterable
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort

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

# RetinaFace-ResNet50 from biubug6/Pytorch_Retinaface (MIT), exported to ONNX.
# Too large for git; setup_ec2.sh downloads it into backend/models/.
RETINAFACE_FILENAME = "retinaface_r50.onnx"
RETINAFACE_SEARCH_PATHS = (
    Path(__file__).resolve().parent.parent / "models" / RETINAFACE_FILENAME,
    Path("/opt/clipnera/models") / RETINAFACE_FILENAME,
)
# Anchor layout and box encoding the network was trained with.
RETINAFACE_STEPS = (8, 16, 32)
RETINAFACE_MIN_SIZES = ((16, 32), (64, 128), (256, 512))
RETINAFACE_VARIANCE = (0.1, 0.2)
RETINAFACE_MEAN_BGR = np.array([104.0, 117.0, 123.0], dtype=np.float32)
# Candidate boxes overlapping more than this are one face; applied before the
# shared post-processing, since every face fires dozens of anchors.
RETINAFACE_NMS_IOU = 0.4

MIN_FACE_CONFIDENCE = 0.6
# Faces smaller than this fraction of frame width are usually background
# bystanders or detector noise, not the subject we should be framing on.
MIN_FACE_WIDTH_RATIO = 0.02
# Detections overlapping more than this are treated as the same face.
DEDUPE_IOU = 0.4
# detect_clip checks YuNet against RetinaFace on one sampled frame in this many
# (about once a second at the cutter's sample rate) ...
PROBE_EVERY = 6
# ... and switches the clip to RetinaFace when more than this share of checks
# disagree. A rare miss is absorbed by track smoothing; a steady one is not.
ESCALATE_RATIO = 0.15
# Two detections of one face from different backends overlap at least this much.
MATCH_IOU = 0.3


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
    """Mouth region spanning the detector's two mouth-corner landmarks."""
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


def _find_model(env_var: str, search_paths: tuple[Path, ...]) -> str | None:
    override = os.getenv(env_var, "").strip()
    candidates = [Path(override)] if override else []
    candidates.extend(search_paths)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


@lru_cache(maxsize=1)
def _yunet_model_path() -> str | None:
    return _find_model("YUNET_MODEL_PATH", YUNET_SEARCH_PATHS)


@lru_cache(maxsize=1)
def _retinaface_session() -> ort.InferenceSession | None:
    """One shared session per process.

    ClipCutter builds a detector per clip; loading 109MB of weights each time
    would cost seconds and double memory with two clips cutting at once.
    InferenceSession.run is thread-safe, so sharing it is fine.
    """
    model_path = _find_model("RETINAFACE_MODEL_PATH", RETINAFACE_SEARCH_PATHS)
    if not model_path:
        return None
    try:
        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    except Exception as exc:
        log.warning("RetinaFace model at %s failed to load: %s", model_path, exc)
        return None
    log.info("Face detection backend: RetinaFace-ResNet50 (%s)", model_path)
    return session


@lru_cache(maxsize=8)
def _retinaface_priors(height: int, width: int) -> np.ndarray:
    """Anchor centres and sizes, normalised, in the order the network emits them."""
    priors: list[tuple[float, float, float, float]] = []
    for step, min_sizes in zip(RETINAFACE_STEPS, RETINAFACE_MIN_SIZES):
        for row in range(math.ceil(height / step)):
            for col in range(math.ceil(width / step)):
                for size in min_sizes:
                    priors.append((
                        (col + 0.5) * step / width,
                        (row + 0.5) * step / height,
                        size / width,
                        size / height,
                    ))
    return np.asarray(priors, dtype=np.float32)


class FaceDetector:
    """Detects faces in BGR frames, normalised to the frame size."""

    def __init__(self, min_confidence: float = MIN_FACE_CONFIDENCE) -> None:
        self._min_confidence = min_confidence
        self._retinaface: ort.InferenceSession | None = None
        self._yunet: Any | None = None
        self._yunet_size: tuple[int, int] | None = None
        self._frontal: Any | None = None
        self._profile: Any | None = None
        self._backend = self._select_backend()

    @property
    def backend(self) -> str:
        return self._backend

    def _select_backend(self) -> str:
        self._retinaface = _retinaface_session()
        self._yunet = self._load_yunet()
        if self._retinaface is not None:
            return "retinaface"
        if self._yunet is not None:
            log.info("Face detection backend: YuNet (%s)", _yunet_model_path())
            return "yunet"

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

    def _load_yunet(self) -> Any | None:
        model_path = _yunet_model_path()
        if not model_path or not hasattr(cv2, "FaceDetectorYN"):
            return None
        try:
            detector = cv2.FaceDetectorYN.create(
                model=model_path,
                config="",
                input_size=(320, 320),
                score_threshold=self._min_confidence,
            )
        except cv2.error as exc:
            log.warning("YuNet unavailable: %s", exc)
            return None
        return detector

    def detect(self, frame: np.ndarray) -> list[Face]:
        if frame is None or getattr(frame, "size", 0) == 0:
            return []
        if self._backend == "retinaface":
            faces = self._detect_retinaface(frame)
        elif self._backend == "yunet":
            faces = self._detect_yunet(frame)
        elif self._backend == "haar":
            faces = self._detect_haar(frame)
        else:
            return []
        kept = self._postprocess(faces)
        log.debug(
            "Face detect (%s): raw=%d kept=%d confidences=%s",
            self._backend, len(faces), len(kept), [round(f.confidence, 2) for f in kept],
        )
        return kept

    def detect_clip(self, frames: Callable[[], Iterable[np.ndarray]]) -> tuple[list[list[Face]], str]:
        """Faces in every frame of one clip, and the backend that produced them.

        RetinaFace is the most accurate backend but ~13x slower than YuNet on
        CPU, and run on every lip-motion sample it was most of a clip's cut
        time. YuNet takes every frame instead, and RetinaFace checks one frame
        in ``PROBE_EVERY``. When the two disagree on more than
        ``ESCALATE_RATIO`` of those checks (small, angled or partly hidden
        faces YuNet misses), RetinaFace redoes the whole clip, so hard clips
        keep full accuracy and easy ones pay only for the checks.

        ``frames`` is called once per pass, so decoded frames never all sit in
        memory at the same time.
        """
        if self._backend != "retinaface" or self._yunet is None:
            return [self.detect(frame) for frame in frames()], self._backend

        fast: list[list[Face]] = []
        accurate: dict[int, list[Face]] = {}
        for index, frame in enumerate(frames()):
            fast.append(self._postprocess(self._detect_yunet(frame)) if _usable(frame) else [])
            if index % PROBE_EVERY == 0:
                accurate[index] = self.detect(frame)

        disagreements = sum(1 for index, faces in accurate.items() if not _same_faces(fast[index], faces))
        if disagreements <= len(accurate) * ESCALATE_RATIO:
            return fast, "yunet"
        log.info(
            "YuNet disagreed with RetinaFace on %d/%d checks; running RetinaFace on every frame",
            disagreements, len(accurate),
        )
        return [
            accurate[index] if index in accurate else self.detect(frame)
            for index, frame in enumerate(frames())
        ], "retinaface"

    def _detect_retinaface(self, frame: np.ndarray) -> list[Face]:
        height, width = frame.shape[:2]
        blob = (frame.astype(np.float32) - RETINAFACE_MEAN_BGR).transpose(2, 0, 1)[np.newaxis]
        try:
            loc, conf, landms = self._retinaface.run(None, {"input": blob})
        except Exception as exc:
            log.warning("RetinaFace detection failed on %dx%d frame: %s", width, height, exc)
            return []

        scores = conf[0][:, 1]
        keep = scores >= self._min_confidence
        if not keep.any():
            return []
        priors = _retinaface_priors(height, width)[keep]
        loc, landms, scores = loc[0][keep], landms[0][keep], scores[keep]

        centre_var, size_var = RETINAFACE_VARIANCE
        centres = priors[:, :2] + loc[:, :2] * centre_var * priors[:, 2:]
        sizes = priors[:, 2:] * np.exp(loc[:, 2:] * size_var)
        corners = centres - sizes / 2
        # Landmarks: eyes, nose, then the two mouth corners (indices 3 and 4).
        points = priors[:, np.newaxis, :2] + landms.reshape(-1, 5, 2) * centre_var * priors[:, np.newaxis, 2:]

        pixel_boxes = [
            [float(x * width), float(y * height), float(w * width), float(h * height)]
            for (x, y), (w, h) in zip(corners, sizes)
        ]
        indices = cv2.dnn.NMSBoxes(pixel_boxes, scores.tolist(), self._min_confidence, RETINAFACE_NMS_IOU)

        faces: list[Face] = []
        for index in np.asarray(indices).reshape(-1):
            (x, y), (w, h) = corners[index], sizes[index]
            box = normalize_box({"x": float(x), "y": float(y), "width": float(w), "height": float(h)})
            if box is None:
                continue
            mouth_left, mouth_right = (tuple(map(float, points[index][i])) for i in (3, 4))
            faces.append(Face(
                box=box,
                confidence=float(scores[index]),
                mouth=_mouth_from_landmarks(box, mouth_left, mouth_right),
            ))
        return faces

    def _detect_yunet(self, frame: np.ndarray) -> list[Face]:
        height, width = frame.shape[:2]
        if self._yunet_size != (width, height):
            self._yunet.setInputSize((width, height))
            self._yunet_size = (width, height)
        try:
            _, detections = self._yunet.detect(frame)
        except cv2.error as exc:
            log.warning("YuNet detection failed on %dx%d frame: %s", width, height, exc)
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


def _usable(frame: np.ndarray | None) -> bool:
    return frame is not None and getattr(frame, "size", 0) > 0


def _same_faces(first: list[Face], second: list[Face]) -> bool:
    """Whether two detections of one frame found the same faces."""
    if len(first) != len(second):
        return False
    unmatched = list(second)
    for face in first:
        match = next((other for other in unmatched if face.box.intersection_over_union(other.box) >= MATCH_IOU), None)
        if match is None:
            return False
        unmatched.remove(match)
    return True
