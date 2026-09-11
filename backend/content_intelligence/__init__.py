from __future__ import annotations

__all__ = [
    "ContentIntelligenceService",
    "FrameAnalyzer",
    "HighlightDetector",
    "TopicResearcher",
    "build_output_formats",
    "build_crop_tracking",
    "crop_for_subject",
    "normalize_box",
]


def __getattr__(name: str):
    if name == "ContentIntelligenceService":
        from .service import ContentIntelligenceService

        return ContentIntelligenceService
    if name == "FrameAnalyzer":
        from .analyzer import FrameAnalyzer

        return FrameAnalyzer
    if name == "HighlightDetector":
        from .highlighter import HighlightDetector

        return HighlightDetector
    if name == "TopicResearcher":
        from .research import TopicResearcher

        return TopicResearcher
    if name in ("build_output_formats", "build_crop_tracking", "crop_for_subject", "normalize_box"):
        from .reframing import (
            build_crop_tracking,
            build_output_formats,
            crop_for_subject,
            normalize_box,
        )

        return {
            "build_output_formats": build_output_formats,
            "build_crop_tracking": build_crop_tracking,
            "crop_for_subject": crop_for_subject,
            "normalize_box": normalize_box,
        }[name]
    raise AttributeError(name)
