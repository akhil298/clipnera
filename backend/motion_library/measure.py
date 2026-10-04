"""Measure a reference reel: its cuts, flashes, tempo and speech, and stills to study.

Run over the inbox with ``python -m motion_library.measure``. Each reel under
``references/`` gets a ``measure/`` folder holding ``measurements.json``, the
sound as ``audio.wav`` and contact sheets of its frames. The numbers are what a
machine can count; what the edit *is* still takes somebody looking at the sheets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import cv2
import librosa
import numpy as np

from motion_library.catalog import library_root
from motion_library.references import MEASURE_DIR, MEASUREMENTS_NAME, NOTES_NAME, REFERENCES_DIR, VIDEO_NAME

AUDIO_NAME = "audio.wav"
AUDIO_RATE = 22050

# Frames are compared at this width; detail finer than this is noise for cut finding.
COMPARE_WIDTH = 160
# A cut is one frame that changes a lot while the frames around it barely do; a fast
# pan changes a lot for many frames in a row, so it is measured against its neighbours.
CUT_PIXEL_CHANGE = 14.0
CUT_TIMES_NEIGHBOURS = 2.5
CUT_NEIGHBOUR_FRAMES = 4
MIN_SHOT_SECONDS = 0.1
# A flash: brightness jumps this far above the half second around it, or the frame is near white.
FLASH_JUMP = 45.0
FLASH_WHITE = 215.0
BLACK_LEVEL = 12.0
# A cut counts as on the beat when it lands within this many seconds of one.
ON_BEAT_SECONDS = 0.09
# The first seconds of a reel, studied frame by frame: where it wins or loses the viewer.
HOOK_SECONDS = 3.0
SHEET_COLUMNS, SHEET_TILES, TILE_LONG_SIDE = 8, 32, 320
LONG_REEL_SECONDS = 25.0
SPEECH_MODEL = "small"
MIN_SPEECH_PROBABILITY = 0.5


def _probe(video: Path) -> dict[str, Any]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    stream = info["streams"][0]
    num, den = (int(n) for n in stream["r_frame_rate"].split("/"))
    width, height = int(stream["width"]), int(stream["height"])
    return {
        "duration_s": round(float(info["format"]["duration"]), 3), "fps": round(num / den, 3),
        "width": width, "height": height,
        "orientation": "portrait" if height > width else "landscape" if width > height else "square",
    }


def _frame_series(video: Path) -> tuple[np.ndarray, np.ndarray, float]:
    """Per frame: mean brightness, and mean pixel change from the frame before."""
    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    brightness, change = [], []
    last = None
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        height = max(1, round(frame.shape[0] * COMPARE_WIDTH / frame.shape[1]))
        small = cv2.resize(frame, (COMPARE_WIDTH, height), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)
        brightness.append(float(gray.mean()))
        change.append(0.0 if last is None else float(np.abs(gray - last).mean()))
        last = gray
    capture.release()
    return np.array(brightness), np.array(change), fps


def _cuts(change: np.ndarray, flashing: np.ndarray, fps: float) -> list[float]:
    """Times where one shot ends and another begins; a flash frame is not a new shot."""
    cuts: list[float] = []
    for i in np.flatnonzero((change > CUT_PIXEL_CHANGE) & ~flashing):
        around = np.concatenate((change[max(0, i - CUT_NEIGHBOUR_FRAMES):i], change[i + 1:i + 1 + CUT_NEIGHBOUR_FRAMES]))
        time = float(i / fps)
        if change[i] >= CUT_TIMES_NEIGHBOURS * np.median(around) and (not cuts or time - cuts[-1] >= MIN_SHOT_SECONDS):
            cuts.append(round(time, 3))
    return cuts


def _flashing(brightness: np.ndarray, fps: float) -> np.ndarray:
    window = max(3, int(fps // 2) | 1)
    padded = np.pad(brightness, window // 2, mode="edge")
    local = np.array([np.median(padded[i:i + window]) for i in range(len(brightness))])
    return ((brightness - local) > FLASH_JUMP) | (brightness > FLASH_WHITE)


def _runs(mask: np.ndarray, fps: float) -> list[dict[str, float]]:
    """Each stretch of consecutive true frames, as a start time and a length."""
    edges = np.flatnonzero(np.diff(np.concatenate(([0], mask.astype(np.int8), [0]))))
    return [
        {"at_s": round(start / fps, 3), "seconds": round((end - start) / fps, 3)}
        for start, end in zip(edges[::2], edges[1::2])
    ]


def _extract_audio(video: Path, target: Path) -> bool:
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", str(AUDIO_RATE), str(target)],
        capture_output=True,
    )
    return done.returncode == 0 and target.is_file()


def _sound(audio: Path) -> dict[str, Any]:
    samples, rate = librosa.load(str(audio), sr=AUDIO_RATE, mono=True)
    if not len(samples) or float(np.abs(samples).max()) < 1e-4:
        return {"silent": True}
    strength = librosa.onset.onset_strength(y=samples, sr=rate)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=strength, sr=rate)
    hits = librosa.onset.onset_detect(onset_envelope=strength, sr=rate, backtrack=False)
    loudness = librosa.feature.rms(y=samples)[0]
    loud_times = librosa.times_like(loudness, sr=rate)
    return {
        "silent": False,
        "bpm": round(float(np.atleast_1d(tempo)[0]), 1),
        "beats_s": [round(float(t), 3) for t in librosa.frames_to_time(beat_frames, sr=rate)],
        "hits_s": [round(float(t), 3) for t in librosa.frames_to_time(hits, sr=rate)],
        "drop_s": _drop(loudness, loud_times),
        # Loudness every half second, 0 to 1, so the shape of the track can be read at a glance.
        "loudness_half_seconds": [
            round(float(loudness[(loud_times >= t) & (loud_times < t + 0.5)].mean() / loudness.max()), 2)
            for t in np.arange(0, loud_times[-1], 0.5)
        ],
    }


def _drop(loudness: np.ndarray, times: np.ndarray) -> float | None:
    """Where the track gets suddenly and lastingly louder: a second after against a second before."""
    best, best_time = 1.8, None
    for t in np.arange(0.5, times[-1] - 1.0, 0.05):
        before = loudness[(times >= t - 1.0) & (times < t)].mean()
        after = loudness[(times >= t) & (times < t + 1.0)].mean()
        if before > 0 and after / before > best:
            best, best_time = after / before, round(float(t), 2)
    return best_time


def _speech(audio: Path) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    model = WhisperModel(SPEECH_MODEL, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio), vad_filter=True, word_timestamps=True)
    words = [
        {"word": w.word.strip(), "start_s": round(w.start, 2), "end_s": round(w.end, 2)}
        for s in segments for w in (s.words or []) if w.probability >= MIN_SPEECH_PROBABILITY
    ]
    return {
        "language": info.language if words else None,
        "text": " ".join(w["word"] for w in words),
        "words": words,
    }


def _on_beat(cuts: list[float], sound: dict[str, Any]) -> float | None:
    marks = np.array(sorted({*sound.get("beats_s", []), *sound.get("hits_s", [])}))
    if not cuts or not len(marks):
        return None
    near = [np.abs(marks - cut).min() <= ON_BEAT_SECONDS for cut in cuts]
    return round(sum(near) / len(near), 2)


def _sheet(video: Path, times: list[float], target: Path, portrait: bool) -> None:
    """One picture of the frames at ``times``, each stamped with its second."""
    capture = cv2.VideoCapture(str(video))
    tiles = []
    for time in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        scale = TILE_LONG_SIDE / max(frame.shape[:2])
        tile = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.rectangle(tile, (0, 0), (62, 18), (0, 0, 0), -1)
        cv2.putText(tile, f"{time:.2f}", (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    capture.release()
    if not tiles:
        return
    columns = SHEET_COLUMNS if portrait else SHEET_COLUMNS // 2
    blank = np.zeros_like(tiles[0])
    tiles += [blank] * (-len(tiles) % columns)
    rows = [np.hstack(tiles[i:i + columns]) for i in range(0, len(tiles), columns)]
    cv2.imwrite(str(target), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])


def _sheets(video: Path, folder: Path, probe: dict[str, Any]) -> list[str]:
    duration, portrait = probe["duration_s"], probe["orientation"] != "landscape"
    per_sheet = SHEET_TILES if portrait else SHEET_TILES // 2
    hook_end = min(HOOK_SECONDS, duration)
    _sheet(video, list(np.linspace(0, hook_end, per_sheet, endpoint=False)), folder / "hook.jpg", portrait)
    names = ["hook.jpg"]
    pages = 1 if duration <= LONG_REEL_SECONDS else 2 if duration <= 2 * LONG_REEL_SECONDS else 4
    times = list(np.linspace(0, duration, per_sheet * pages, endpoint=False))
    for page in range(pages):
        name = f"full_{page + 1}.jpg"
        _sheet(video, times[page * per_sheet:(page + 1) * per_sheet], folder / name, portrait)
        names.append(name)
    return names


def measure(folder: Path) -> dict[str, Any]:
    """Measure the reel in ``folder`` and write the results beside it."""
    video, out = folder / VIDEO_NAME, folder / MEASURE_DIR
    out.mkdir(exist_ok=True)
    probe = _probe(video)
    brightness, change, fps = _frame_series(video)
    flashing = _flashing(brightness, fps)
    cuts = _cuts(change, flashing, fps)
    shots = np.diff([0.0, *cuts, probe["duration_s"]])
    has_audio = _extract_audio(video, out / AUDIO_NAME)
    sound = _sound(out / AUDIO_NAME) if has_audio else {"silent": True}
    result = {
        "id": folder.name,
        **probe,
        "cuts_s": cuts,
        "shot_count": len(shots),
        "median_shot_s": round(float(np.median(shots)), 2),
        "shortest_shot_s": round(float(shots.min()), 2),
        "cuts_in_hook": sum(1 for cut in cuts if cut < HOOK_SECONDS),
        "cuts_on_beat": _on_beat(cuts, sound),
        "flashes": _runs(flashing, fps),
        "black_frames": _runs(brightness < BLACK_LEVEL, fps),
        # Movement every half second, 0 to 1: where the picture is busy and where it rests.
        "movement_half_seconds": [
            round(float(chunk.mean() / max(change.max(), 1e-6)), 2)
            for chunk in np.array_split(change, max(1, round(probe["duration_s"] * 2)))
        ],
        "sound": sound,
        "speech": _speech(out / AUDIO_NAME) if not sound["silent"] else {"language": None, "text": "", "words": []},
        "sheets": _sheets(video, out, probe),
    }
    (out / MEASUREMENTS_NAME).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def pending(root: Path) -> list[Path]:
    """Reels in the inbox that are whole and not yet measured."""
    inbox = root / REFERENCES_DIR
    if not inbox.is_dir():
        return []
    return sorted(
        folder for folder in inbox.iterdir()
        if (folder / VIDEO_NAME).is_file() and (folder / NOTES_NAME).is_file()
        and not (folder / MEASURE_DIR / MEASUREMENTS_NAME).is_file()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="Reel ids to measure; all unmeasured reels when omitted.")
    args = parser.parse_args()
    root = library_root()
    folders = [root / REFERENCES_DIR / id_ for id_ in args.ids] or pending(root)
    for folder in folders:
        result = measure(folder)
        print(f"{result['id']}: {result['duration_s']}s, {result['shot_count']} shots, "
              f"{result['sound'].get('bpm', '-')} bpm, speech: {result['speech']['text'][:60]!r}")


if __name__ == "__main__":
    main()
