from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)


class CheckpointManager:
    @staticmethod
    def save(
        checkpoint_path: str,
        input_path: str,
        processed_chunks: list[dict],
        all_segments: list[dict],
        language: str,
        model_size: str,
    ) -> None:
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_path": input_path,
            "language": language,
            "model_size": model_size,
            "processed_chunks": processed_chunks,
            "segments": all_segments,
        }
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        log.debug(f"Checkpoint saved: {checkpoint_path}")

    @staticmethod
    def load(checkpoint_path: str) -> dict[str, Any] | None:
        if not os.path.exists(checkpoint_path):
            return None
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning(f"Failed to load checkpoint {checkpoint_path}: {exc}")
            return None

    @staticmethod
    def cleanup(checkpoint_path: str) -> None:
        try:
            if os.path.exists(checkpoint_path):
                os.remove(checkpoint_path)
        except Exception as exc:
            log.warning(f"Failed to cleanup checkpoint {checkpoint_path}: {exc}")
