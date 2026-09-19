from __future__ import annotations

import pytest

from core.exceptions import CustomException
from pipeline.model import PipelineStepType
from pipeline.route import RUNNABLE_PIPELINE_STEPS, _resolve_steps


class TestStepResolution:
    def test_drops_steps_with_no_handler(self):
        # Regression: the upload flow sent "bounding_box_detection", which the
        # orchestrator never runs. Its step row stayed "pending" forever, so the
        # UI showed a stuck step and overall progress never reached 100%.
        resolved = _resolve_steps([
            "audio_extraction", "bounding_box_detection", "transcription", "clip_generation",
        ])

        assert PipelineStepType.BOUNDING_BOX_DETECTION not in resolved
        assert [s.value for s in resolved] == [
            "audio_extraction", "transcription", "clip_generation",
        ]

    def test_drops_unknown_step_names(self):
        resolved = _resolve_steps(["audio_extraction", "not_a_step"])
        assert [s.value for s in resolved] == ["audio_extraction"]

    def test_resolves_aliases(self):
        resolved = _resolve_steps(["auto_reframe", "caption_styling"])
        assert [s.value for s in resolved] == ["aspect_ratio_render", "subtitle_styling"]

    def test_deduplicates_while_preserving_order(self):
        resolved = _resolve_steps(["transcription", "audio_extraction", "transcription"])
        assert [s.value for s in resolved] == ["transcription", "audio_extraction"]

    def test_rejects_a_request_with_nothing_runnable(self):
        with pytest.raises(CustomException) as excinfo:
            _resolve_steps(["bounding_box_detection", "download"])
        assert excinfo.value.code == "NO_RUNNABLE_STEPS"

    def test_every_runnable_step_has_an_orchestrator_handler(self):
        # Keeps the allow-list honest: adding a step here without wiring a
        # handler would reintroduce the permanently-pending step bug.
        from pipeline.service import PipelineOrchestrator

        orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
        handler_names = {
            f"_step_{step.value}" for step in RUNNABLE_PIPELINE_STEPS
        }
        missing = [name for name in handler_names if not hasattr(orchestrator, name)]
        assert missing == []
