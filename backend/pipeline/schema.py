from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PipelineStartRequest(BaseModel):
    """Settings for a pipeline run, as /pipeline/start reads them.

    Also sent with a YouTube download or an upload, so the server starts the
    run itself once the source is stored rather than waiting for the browser.
    """

    steps: list[str] | None = None
    audio_config: dict[str, Any] | None = None
    output_aspect_ratios: list[str] | None = None
    clip_settings: dict[str, Any] | None = None
    watermark_enabled: bool | None = None

    def body(self) -> dict[str, Any]:
        """The run body PipelineRunService takes; unset fields keep their defaults."""
        return self.model_dump(exclude_none=True)
