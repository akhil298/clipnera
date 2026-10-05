"""Speaker diarization in its own process: ``python -m transcription.diarize_worker AUDIO OUT``.

pyannote loads torch and about a gigabyte of model weights. Run inside the API
or worker process, that memory stayed allocated after the run ended (Python
rarely hands freed memory back to the OS), so every process that had ever
diarized sat at its peak. A child process returns all of it when it exits, and
the parent can stop it when it runs too long.

:func:`diarize` is the parent's side; :func:`main` runs in the child and
writes the speaker turns to ``OUT`` as JSON.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
# No min_speakers: forcing two split every solo talker into two people.
MAX_SPEAKERS = 6


def thread_count() -> int:
    """Torch threads for the child: DIARIZATION_THREADS, or every core but one."""
    configured = int(getattr(get_settings(), "DIARIZATION_THREADS", 0) or 0)
    return configured if configured > 0 else max(1, (os.cpu_count() or 2) - 1)


async def diarize(audio_path: str) -> list[dict[str, Any]]:
    """Speaker turns for ``audio_path``, or [] when diarization is off, fails or runs too long."""
    settings = get_settings()
    if not (settings.HF_TOKEN or "").strip():
        log.warning("HF_TOKEN not set; diarization disabled")
        return []
    timeout = max(1, int(settings.DIARIZATION_TIMEOUT_SECONDS))
    with tempfile.TemporaryDirectory() as workdir:
        out = Path(workdir) / "turns.json"
        # The child reads the token from settings itself, so it never appears
        # in the process list.
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "transcription.diarize_worker", audio_path, str(out),
            cwd=str(BACKEND_DIR),
            env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            log.warning("Diarization ran past %ds and was stopped; continuing without speaker labels", timeout)
            return []
        except asyncio.CancelledError:
            proc.kill()
            raise
        if proc.returncode != 0 or not out.exists():
            log.warning("Diarization process failed (exit %s): %s", proc.returncode, stderr.decode(errors="ignore")[-500:])
            return []
        return json.loads(out.read_text())


def turns_from(diarize_model: Any, audio_path: str) -> list[dict[str, Any]]:
    import librosa

    audio, _ = librosa.load(audio_path, sr=16000)
    turns = diarize_model(audio, max_speakers=MAX_SPEAKERS)
    if hasattr(turns, "to_dict"):
        turns = turns.to_dict("records")
    return [
        {"start": float(t.get("start", 0.0)), "end": float(t.get("end", 0.0)), "speaker": str(t.get("speaker"))}
        for t in (turns or [])
    ]


def main(audio_path: str, out_path: str) -> None:
    import torch

    torch.set_num_threads(thread_count())
    from whisperx.diarize import DiarizationPipeline

    model = DiarizationPipeline(use_auth_token=get_settings().HF_TOKEN.strip(), device="cpu")
    Path(out_path).write_text(json.dumps(turns_from(model, audio_path)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
