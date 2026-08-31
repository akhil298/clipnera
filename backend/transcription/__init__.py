from __future__ import annotations

import os

from transcription.chunker import TranscriptionChunker

TranscriptionChunker.estimate_duration = staticmethod(lambda path: TranscriptionChunker._estimate_duration(path))
