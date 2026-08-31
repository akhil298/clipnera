from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)


class TranscriptionFormatter:
    @staticmethod
    def seconds_to_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def seconds_to_vtt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    @staticmethod
    def to_srt(segments: list[dict], output_path: str) -> str:
        lines = []
        for idx, seg in enumerate(segments, 1):
            start = TranscriptionFormatter.seconds_to_srt_time(seg["start"])
            end = TranscriptionFormatter.seconds_to_srt_time(seg["end"])
            text = seg.get("text", "").strip()
            speaker = seg.get("speaker")
            if speaker:
                text = f"<b>{speaker}:</b> {text}"
            lines.append(f"{idx}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.debug(f"SRT written: {output_path}")
        return output_path

    @staticmethod
    def to_vtt(segments: list[dict], output_path: str) -> str:
        lines = ["WEBVTT", ""]
        for idx, seg in enumerate(segments, 1):
            start = TranscriptionFormatter.seconds_to_vtt_time(seg["start"])
            end = TranscriptionFormatter.seconds_to_vtt_time(seg["end"])
            text = seg.get("text", "").strip()
            speaker = seg.get("speaker")
            if speaker:
                text = f"<b>{speaker}:</b> {text}"
            lines.append(f"{idx}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.debug(f"VTT written: {output_path}")
        return output_path

    @staticmethod
    def to_txt(segments: list[dict], output_path: str) -> str:
        lines = []
        current_speaker = None
        for seg in segments:
            text = seg.get("text", "").strip()
            speaker = seg.get("speaker")
            if speaker and speaker != current_speaker:
                lines.append(f"\n[{speaker}]\n")
                current_speaker = speaker
            lines.append(text)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.debug(f"TXT written: {output_path}")
        return output_path

    @staticmethod
    def to_json(segments: list[dict], output_path: str, metadata: dict[str, Any]) -> str:
        payload = {
            "metadata": metadata,
            "segments": segments,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        log.debug(f"JSON written: {output_path}")
        return output_path

    @staticmethod
    def write_outputs(segments: list[dict], output_dir: str, base_name: str, output_format: str, metadata: dict[str, Any]) -> dict[str, str]:
        outputs = {}
        os.makedirs(output_dir, exist_ok=True)
        base_path = os.path.join(output_dir, base_name)
        if output_format in ("srt", "all"):
            outputs["srt"] = TranscriptionFormatter.to_srt(segments, f"{base_path}.srt")
        if output_format in ("vtt", "all"):
            outputs["vtt"] = TranscriptionFormatter.to_vtt(segments, f"{base_path}.vtt")
        if output_format in ("txt", "all"):
            outputs["txt"] = TranscriptionFormatter.to_txt(segments, f"{base_path}.txt")
        if output_format in ("json", "all"):
            outputs["json"] = TranscriptionFormatter.to_json(segments, f"{base_path}.json", metadata)
        return outputs
