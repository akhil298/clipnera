from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from pipeline.model import PipelineStepType


def test_pipeline_step_types():
    assert PipelineStepType.DOWNLOAD.value == "download"
    assert PipelineStepType.TRANSCRIPTION.value == "transcription"
    assert PipelineStepType.HIGHLIGHT_DETECTION.value == "highlight_detection"
    assert PipelineStepType.BURN_IN_EXPORT.value == "burn_in_export"


def test_pipeline_step_migration_includes_render_and_box_values():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20250904140000_add_missing_pipeline_step_types.py"
    source = migration_path.read_text(encoding="utf-8")
    assert "aspect_ratio_render" in source
    assert "bounding_box_detection" in source


def test_pipeline_step_order():
    steps = [
        PipelineStepType.DOWNLOAD,
        PipelineStepType.AUDIO_EXTRACTION,
        PipelineStepType.AI_NOISE_CANCELLATION,
        PipelineStepType.TRANSCRIPTION,
        PipelineStepType.TOPIC_RESEARCH,
        PipelineStepType.VISUAL_ANALYSIS,
        PipelineStepType.CONTENT_CLASSIFICATION,
        PipelineStepType.HIGHLIGHT_DETECTION,
        PipelineStepType.SCORING,
        PipelineStepType.METADATA_GENERATION,
        PipelineStepType.CLIP_GENERATION,
        PipelineStepType.SUBTITLE_STYLING,
        PipelineStepType.BURN_IN_EXPORT,
    ]
    assert len(steps) == 13
    assert steps[0] == PipelineStepType.DOWNLOAD
    assert steps[-1] == PipelineStepType.BURN_IN_EXPORT
