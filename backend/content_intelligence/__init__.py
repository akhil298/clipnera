from __future__ import annotations

__all__ = [
    "ContentIntelligenceService",
    "FrameAnalyzer",
    "HighlightDetector",
    "TopicResearcher",
    "LayoutAnalyzer",
    "ContentImportanceAnalyzer",
    "CropStrategySelector",
    "LayoutDecision",
    "ImportanceMap",
    "RegionImportance",
    "CropStrategy",
    "CropResult",
    "SceneContext",
    "SafeFallbackStrategy",
    "SingleSubjectStrategy",
    "TopBottomSpeakerStrategy",
    "LeftRightSpeakerStrategy",
    "GamingStrategy",
    "ScreenShareStrategy",
    "MultiSubjectStrategy",
    "NoChangeStrategy",
    "build_smart_output_formats",
    "build_crop_tracking",
    "crop_for_subject",
    "normalize_box",
    "SUPPORTED_LAYOUTS",
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
    if name == "LayoutAnalyzer":
        from .layout_analyzer import LayoutAnalyzer
        return LayoutAnalyzer
    if name == "LayoutDecision":
        from .layout_analyzer import LayoutDecision
        return LayoutDecision
    if name == "SUPPORTED_LAYOUTS":
        from .layout_analyzer import SUPPORTED_LAYOUTS
        return SUPPORTED_LAYOUTS
    if name == "ContentImportanceAnalyzer":
        from .content_importance import ContentImportanceAnalyzer
        return ContentImportanceAnalyzer
    if name == "ImportanceMap":
        from .content_importance import ImportanceMap
        return ImportanceMap
    if name == "RegionImportance":
        from .content_importance import RegionImportance
        return RegionImportance
    if name == "CropStrategySelector":
        from .crop_strategy import CropStrategySelector
        return CropStrategySelector
    if name == "CropStrategy":
        from .crop_strategy import CropStrategy
        return CropStrategy
    if name == "CropResult":
        from .crop_strategy import CropResult
        return CropResult
    if name == "SceneContext":
        from .crop_strategy import SceneContext
        return SceneContext
    if name == "SafeFallbackStrategy":
        from .crop_strategy import SafeFallbackStrategy
        return SafeFallbackStrategy
    if name == "SingleSubjectStrategy":
        from .crop_strategy import SingleSubjectStrategy
        return SingleSubjectStrategy
    if name == "TopBottomSpeakerStrategy":
        from .crop_strategy import TopBottomSpeakerStrategy
        return TopBottomSpeakerStrategy
    if name == "LeftRightSpeakerStrategy":
        from .crop_strategy import LeftRightSpeakerStrategy
        return LeftRightSpeakerStrategy
    if name == "GamingStrategy":
        from .crop_strategy import GamingStrategy
        return GamingStrategy
    if name == "ScreenShareStrategy":
        from .crop_strategy import ScreenShareStrategy
        return ScreenShareStrategy
    if name == "MultiSubjectStrategy":
        from .crop_strategy import MultiSubjectStrategy
        return MultiSubjectStrategy
    if name == "NoChangeStrategy":
        from .crop_strategy import NoChangeStrategy
        return NoChangeStrategy
    if name == "build_smart_output_formats":
        from .reframing import build_smart_output_formats
        return build_smart_output_formats
    if name == "build_crop_tracking":
        from .reframing import _build_crop_tracking
        return _build_crop_tracking
    if name == "crop_for_subject":
        from .reframing import crop_for_subject
        return crop_for_subject
    if name == "normalize_box":
        from .reframing import normalize_box
        return normalize_box
    raise AttributeError(name)
