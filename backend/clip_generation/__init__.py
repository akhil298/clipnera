from __future__ import annotations

__all__ = [
    "ClipRepository",
    "ClipService",
    "ContentCategory",
    "GeneratedClip",
    "SubtitleStyle",
]


def __getattr__(name: str):
    if name in ("GeneratedClip", "ContentCategory"):
        from .model import GeneratedClip, ContentCategory

        return {"GeneratedClip": GeneratedClip, "ContentCategory": ContentCategory}[name]
    if name == "SubtitleStyle":
        from subtitle_styling.model import SubtitleStyle

        return SubtitleStyle
    if name == "ClipRepository":
        from .repository import ClipRepository

        return ClipRepository
    if name == "ClipService":
        from .service import ClipService

        return ClipService
    raise AttributeError(name)
