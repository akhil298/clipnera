from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from formats import VisualEvidence, evidence_from_dict
from formats.visual_probe import (
    EVIDENCE_PROMPT_CHARS,
    PROBE_WINDOW_SECONDS,
    _add_facecam,
    _aligned_text_lines,
    _chroma_green,
    _content_beside,
    _face_signature,
    _Sample,
    _same_face,
    _screen_like,
    _windows,
    evidence_prompt,
    probe_video,
)
from video_processor.geometry import Box

# editing.thumbnail's shape (rows, columns).
THUMB_SHAPE = (36, 64)


def _document(width: int = 640, height: int = 360) -> np.ndarray:
    """A white page of left-aligned text lines, like a document or slide."""
    frame = np.full((height, width, 3), 255, np.uint8)
    for row in range(10):
        cv2.putText(frame, "def measure(frame): return the share", (24, 30 + row * 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    return frame


def _footage(width: int = 640, height: int = 360, seed: int = 0) -> np.ndarray:
    """Camera-like footage: smooth gradients under sensor noise and blobs of texture."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, width)[None, :, None]
    y = np.linspace(0, 1, height)[:, None, None]
    frame = 60 + 120 * x * np.array([0.4, 0.7, 1.0]) + 60 * y * np.array([1.0, 0.5, 0.3])
    frame = frame + rng.normal(0, 6, (height, width, 3))
    for _ in range(25):
        cx, cy, r = rng.integers(0, width), rng.integers(0, height), rng.integers(10, 60)
        cv2.circle(frame, (int(cx), int(cy)), int(r), rng.integers(0, 255, 3).tolist(), -1)
    return np.clip(cv2.GaussianBlur(frame, (5, 5), 0) + rng.normal(0, 4, (height, width, 3)), 0, 255).astype(np.uint8)


def _no_person(frame: np.ndarray) -> np.ndarray:
    return np.zeros(frame.shape[:2], np.uint8)


def test_text_page_reads_as_screen_and_footage_does_not():
    page = _document()
    assert _aligned_text_lines(cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)) >= 4
    assert _screen_like(page, cv2.cvtColor(page, cv2.COLOR_BGR2GRAY))
    for seed in range(3):
        footage = _footage(seed=seed)
        assert not _screen_like(footage, cv2.cvtColor(footage, cv2.COLOR_BGR2GRAY))


def test_flat_chroma_green_reads_as_green_screen_but_foliage_does_not():
    backdrop = np.zeros((360, 640, 3), np.uint8)
    backdrop[:] = (60, 190, 40)
    backdrop = np.clip(backdrop + np.random.default_rng(0).normal(0, 1.5, backdrop.shape), 0, 255).astype(np.uint8)
    assert _chroma_green(backdrop, cv2.cvtColor(backdrop, cv2.COLOR_BGR2GRAY), _no_person(backdrop))

    rng = np.random.default_rng(1)
    hsv = np.dstack([rng.integers(35, 85, (360, 640)), rng.integers(120, 255, (360, 640)),
                     rng.integers(50, 255, (360, 640))]).astype(np.uint8)
    foliage = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    assert not _chroma_green(foliage, cv2.cvtColor(foliage, cv2.COLOR_BGR2GRAY), _no_person(foliage))

    footage = _footage()
    assert not _chroma_green(footage, cv2.cvtColor(footage, cv2.COLOR_BGR2GRAY), _no_person(footage))


def test_face_signature_matches_a_mirrored_copy_but_not_other_texture():
    gray = cv2.cvtColor(_footage(seed=4), cv2.COLOR_BGR2GRAY)
    box = Box(0.3, 0.2, 0.3, 0.5)
    mirrored = gray.copy()
    mirrored[72:252, 192:384] = gray[72:252, 192:384][:, ::-1]
    assert _same_face(_face_signature(gray, box), _face_signature(gray, box))
    assert _same_face(_face_signature(gray, box), _face_signature(mirrored, box))
    other = cv2.cvtColor(_document(), cv2.COLOR_BGR2GRAY)
    assert not _same_face(_face_signature(gray, box), _face_signature(other, box))
    assert not _same_face(None, _face_signature(gray, box))


def test_content_beside_a_small_overlay_is_the_whole_frame():
    assert _content_beside(Box(0.8, 0.75, 0.15, 0.2)) == Box()
    side = _content_beside(Box(0.0, 0.0, 0.35, 1.0))
    assert side.x == pytest.approx(0.35) and side.width == pytest.approx(0.65)


def _sample(index: int, timestamp: float, faces: list[Box], continues: bool = True, **flags) -> _Sample:
    return _Sample(index=index, timestamp=timestamp, size=(640, 360), faces=faces, continues=continues, **flags)


def test_facecam_found_when_a_corner_face_holds_across_cuts():
    cam = Box(0.85, 0.75, 0.06, 0.1)
    samples = [_sample(i, i * 2.0, [cam], continues=i % 3 != 0) for i in range(12)]
    evidence = VisualEvidence(0.0, 24.0)
    _add_facecam(evidence, samples)
    assert evidence.facecam == pytest.approx(1.0)
    assert evidence.facecam_box is not None and evidence.content_box == (0.0, 0.0, 1.0, 1.0)


def test_small_face_in_a_still_shot_is_not_a_facecam():
    still = np.full(THUMB_SHAPE, 90, np.uint8)
    samples = [_sample(i, i * 2.0, [Box(0.45, 0.3, 0.06, 0.1)], thumb=still) for i in range(12)]
    evidence = VisualEvidence(0.0, 24.0)
    _add_facecam(evidence, samples)
    assert evidence.facecam == 0.0 and evidence.facecam_box is None


def test_windows_aggregate_shares_lip_sync_and_fill_gaps():
    face = Box(0.4, 0.2, 0.2, 0.35)
    samples = [
        _sample(0, 1.0, [face], talking=True, screen=True),
        _sample(1, 3.0, [face], talking=False),
        _sample(2, 5.0, [], green=True),
        _sample(3, 7.0, [face, Box(0.1, 0.2, 0.18, 0.3)], talking=True, two_faces=True),
        # Nothing sampled in 30-60s; 60-75s has one faceless sample.
        _sample(4, 61.0, []),
    ]
    speech = [(0.0, 10.0)]
    windows = _windows(samples, [5.0], 75.0, speech)
    assert [(w.start, w.end) for w in windows] == [(0.0, 30.0), (30.0, 60.0), (60.0, 75.0)]
    first = windows[0]
    assert first.face == pytest.approx(0.75)
    assert first.two_faces == pytest.approx(0.25)
    assert first.screen == pytest.approx(0.25)
    assert first.green == pytest.approx(0.25)
    # Talking in 2 of 4 speech samples: the faceless one counts as not talking.
    assert first.lip_sync == pytest.approx(0.5)
    assert first.cuts_per_minute == pytest.approx(2.0)
    assert windows[1].face == first.face and windows[1].start == 30.0
    assert windows[2].face == 0.0 and windows[2].lip_sync == 1.0


def test_lip_sync_without_transcript_follows_faces():
    face = Box(0.4, 0.2, 0.2, 0.35)
    windows = _windows([_sample(0, 1.0, [face]), _sample(1, 31.0, [])], [], 60.0, None)
    assert [w.lip_sync for w in windows] == [1.0, 0.0]


def test_evidence_round_trips_and_prompt_stays_short():
    windows = []
    for index in range(120):
        start = index * PROBE_WINDOW_SECONDS
        talking = index % 2 == 0
        windows.append(VisualEvidence(
            start=start, end=start + PROBE_WINDOW_SECONDS, face=1.0 if talking else 0.6, screen=0.0 if talking else 0.9,
            facecam=0.0 if talking else 0.8, facecam_box=None if talking else (0.75, 0.7, 0.2, 0.25),
        ))
    assert evidence_from_dict(windows[1].as_dict()) == windows[1]
    prompt = evidence_prompt(windows)
    assert len(prompt) <= EVIDENCE_PROMPT_CHARS
    assert "0:00-0:30 one face, talking" in prompt
    assert "screen recording or slides with webcam bottom-right" in prompt
    assert evidence_prompt([]) == ""


@pytest.fixture(scope="module")
def tiny_video(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("probe") / "testsrc.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10",
        "-t", "40", "-c:v", "libx264", "-g", "20", "-pix_fmt", "yuv420p", str(path),
    ], check=True)
    return path


@pytest.mark.asyncio
async def test_probe_video_end_to_end(tiny_video: Path):
    windows = await probe_video(str(tiny_video), 40.0, [{"start": 0.0, "end": 40.0, "text": "hello there"}])
    assert [(w.start, w.end) for w in windows] == [(0.0, 30.0), (30.0, 40.0)]
    assert all(w.face == 0.0 for w in windows)
    assert "no face" in evidence_prompt(windows)


@pytest.mark.asyncio
async def test_probe_video_never_raises(tmp_path: Path):
    assert await probe_video(str(tmp_path / "missing.mp4"), 30.0) == []
    assert await probe_video(str(tmp_path / "missing.mp4"), 0.0) == []
