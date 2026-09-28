"""What each plan may do with footage reels, from the plan's entitlements and settings."""

from __future__ import annotations

from dataclasses import dataclass

from core.config import get_settings
from subscription.entitlements import Entitlements

FREE_SIZE = (720, 1280)
PRO_SIZE = (1080, 1920)


@dataclass(frozen=True)
class EditLimits:
    max_raw_seconds: int
    max_files: int
    max_output_seconds: int
    max_chat_edits: int
    size: tuple[int, int]


def limits_for(entitlements: Entitlements) -> EditLimits:
    settings = get_settings()
    if entitlements.pro_ai_provider:
        return EditLimits(settings.EDIT_MAX_RAW_SECONDS_PRO, settings.EDIT_MAX_FILES_PRO,
                          settings.EDIT_MAX_OUTPUT_SECONDS_PRO, settings.EDIT_MAX_CHAT_EDITS_PRO, PRO_SIZE)
    return EditLimits(settings.EDIT_MAX_RAW_SECONDS_FREE, settings.EDIT_MAX_FILES_FREE,
                      settings.EDIT_MAX_OUTPUT_SECONDS_FREE, settings.EDIT_MAX_CHAT_EDITS_FREE, FREE_SIZE)
