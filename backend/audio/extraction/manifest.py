from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)


class ManifestGenerator:
    @staticmethod
    def generate(
        input_path: str,
        output_path: str,
        source_duration: float,
        output_duration: float,
        sample_rate: int,
        channels: int,
        codec: str,
        format: str,
        file_size_bytes: int,
        warnings: list[str],
        processing_time_seconds: float,
        status: str = "completed",
        error: str | None = None,
    ) -> dict[str, Any]:
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": {
                "path": input_path,
                "duration_seconds": round(source_duration, 3),
            },
            "output": {
                "path": output_path,
                "duration_seconds": round(output_duration, 3),
                "sample_rate": sample_rate,
                "channels": channels,
                "codec": codec,
                "format": format,
                "file_size_bytes": file_size_bytes,
            },
            "processing": {
                "time_seconds": round(processing_time_seconds, 3),
                "status": status,
            },
            "warnings": warnings,
        }
        if error:
            manifest["error"] = error
        return manifest

    @staticmethod
    def save(manifest: dict[str, Any], output_path: str) -> str:
        base, _ = os.path.splitext(output_path)
        manifest_path = f"{base}.manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        log.debug(f"Manifest saved: {manifest_path}")
        return manifest_path

    @staticmethod
    def validate_sync(source_duration: float, output_duration: float, tolerance: float = 0.1) -> str | None:
        drift = abs(source_duration - output_duration)
        if drift > tolerance:
            return (
                f"Audio sync drift detected: source={source_duration:.3f}s, "
                f"output={output_duration:.3f}s, drift={drift:.3f}s (tolerance={tolerance}s)"
            )
        return None
