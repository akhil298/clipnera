from __future__ import annotations

import numpy as np

from video_processor.face_detection import PROBE_EVERY, Face, FaceDetector
from video_processor.geometry import Box


def face_at(x: float, size: float = 0.2) -> Face:
    box = Box(x, 0.3, size, size)
    return Face(box=box, confidence=0.9, mouth=Box(x + size / 4, 0.3 + size * 0.62, size / 2, size / 4))


class StubDetector(FaceDetector):
    """Both backends loaded, answering from fixed per-frame results."""

    def __init__(self, yunet: list[list[Face]], retinaface: list[list[Face]]) -> None:
        self._min_confidence = 0.6
        self._backend = "retinaface"
        self._yunet = object()
        self._answers = {"yunet": yunet, "retinaface": retinaface}
        self.calls = {"yunet": 0, "retinaface": 0}

    def _answer(self, backend: str, frame: np.ndarray) -> list[Face]:
        self.calls[backend] += 1
        return self._answers[backend][int(frame[0, 0, 0])]

    def _detect_yunet(self, frame: np.ndarray) -> list[Face]:
        return self._answer("yunet", frame)

    def _detect_retinaface(self, frame: np.ndarray) -> list[Face]:
        return self._answer("retinaface", frame)


def frames(count: int):
    return lambda: (np.full((4, 4, 3), index, dtype=np.uint8) for index in range(count))


def test_agreeing_backends_keep_yunet_and_only_probe_retinaface() -> None:
    count = PROBE_EVERY * 5
    same = [[face_at(0.4)] for _ in range(count)]
    detector = StubDetector(yunet=same, retinaface=same)

    faces, backend = detector.detect_clip(frames(count))

    assert backend == "yunet"
    assert len(faces) == count
    assert detector.calls == {"yunet": count, "retinaface": 5}


def test_steady_misses_escalate_the_clip_to_retinaface() -> None:
    count = PROBE_EVERY * 5
    both = [face_at(0.1), face_at(0.6)]
    detector = StubDetector(
        yunet=[[face_at(0.1)] for _ in range(count)],
        retinaface=[both for _ in range(count)],
    )

    faces, backend = detector.detect_clip(frames(count))

    assert backend == "retinaface"
    assert all(len(frame_faces) == 2 for frame_faces in faces)
    # Probed frames are reused, not detected twice.
    assert detector.calls["retinaface"] == count


def test_a_rare_miss_does_not_escalate() -> None:
    count = PROBE_EVERY * 10
    yunet = [[face_at(0.4)] for _ in range(count)]
    yunet[0] = []
    detector = StubDetector(yunet=yunet, retinaface=[[face_at(0.4)] for _ in range(count)])

    _, backend = detector.detect_clip(frames(count))

    assert backend == "yunet"


def test_shifted_detections_count_as_disagreement() -> None:
    count = PROBE_EVERY * 2
    detector = StubDetector(
        yunet=[[face_at(0.1)] for _ in range(count)],
        retinaface=[[face_at(0.7)] for _ in range(count)],
    )

    _, backend = detector.detect_clip(frames(count))

    assert backend == "retinaface"
