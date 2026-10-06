"""Copy the curated sound effects from the owner's asset library into the backend.

The library (``backend/static/motion/library/sound_effect/``, ~39 GB) never
ships to servers, so the handful of sounds motion graphics use are trimmed,
peak-normalised and written to ``static/motion/sfx`` with a manifest recording
where each sound's peak falls, which is what gets lined up with its visual event.

Recognisable game and meme audio in the library (GTA, Mario, Pac-Man, Among Us,
anime and vine clips) is someone else's copyrighted sound and is left out.

    cd backend && venv/bin/python scripts/build_motion_sfx.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
LIBRARY = BACKEND / "static" / "motion" / "library" / "sound_effect"
OUT = BACKEND / "static" / "motion" / "sfx"
SAMPLE_RATE = 48000
PEAK_DB = -1.0

# name -> (library file, longest kept seconds, licence note)
SOUNDS: dict[str, tuple[str, float, str]] = {
    "pop": ("SFX/General SFX/Pop sound effect 1pop up sound effectpop smokeballon pop sound effectpop sound effect youtuber.mp3",
            0.6, "owner library, generic pop"),
    "click": ("SFX/trending sfx/click-button.mp3", 0.4, "owner library, generic UI click"),
    "soft_click": ("drive-download-20261004T045104Z-1-001/interface-soft-click-131438 (1).mp3", 0.5,
                   "Pixabay content licence"),
    "whoosh": ("drive-download-20261004T045104Z-1-001/mixkit-flying-fast-swoosh-1469.wav", 1.2, "Mixkit free licence"),
    "whoosh_short": ("SFX/trending sfx/Short whoose_1.mp3", 0.8, "owner library, generic whoosh"),
    "ding": ("SFX/trending sfx/Correct.mp3", 0.9, "owner library, generic chime"),
    "cash": ("SFX/trending sfx/Cash Register.wav", 1.2, "owner library, generic register"),
    "tick": ("SFX/trending sfx/counting.wav", 0.6, "owner library, generic counter"),
    "boom": ("SFX/trending sfx/Cinematic_boom_01.wav", 2.5, "owner library, generic cinematic boom"),
    "riser": ("SFX/trending sfx/riser.mp3", 3.0, "owner library, generic riser"),
}


def _decode(path: Path, seconds: float) -> np.ndarray:
    """Mono float samples of ``path``, leading silence trimmed, at most ``seconds`` long."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-af", "silenceremove=start_periods=1:start_threshold=-45dB",
         "-t", f"{seconds}", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.float32)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {}
    for name, (source, seconds, licence) in SOUNDS.items():
        samples = _decode(LIBRARY / source, seconds)
        if samples.size == 0:
            raise SystemExit(f"{name}: no audio in {source}")
        peak_index = int(np.argmax(np.abs(samples)))
        gain = 10 ** (PEAK_DB / 20) / max(1e-6, float(np.abs(samples).max()))
        fade = min(len(samples), SAMPLE_RATE // 20)
        shaped = samples * gain
        shaped[-fade:] *= np.linspace(1.0, 0.0, fade)
        target = OUT / f"{name}.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "pipe:0",
             "-c:a", "pcm_s16le", str(target)],
            input=shaped.astype(np.float32).tobytes(), check=True,
        )
        manifest[name] = {
            "file": target.name,
            "seconds": round(len(samples) / SAMPLE_RATE, 3),
            "peak": round(peak_index / SAMPLE_RATE, 3),
            "source": source,
            "licence": licence,
        }
        print(f"{name:13s} {manifest[name]['seconds']:.2f}s peak@{manifest[name]['peak']:.3f}s  <- {source}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build()
