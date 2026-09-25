from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from hook_transitions.catalog import (
    EFFECTS,
    FRAMING_EFFECTS,
    IMPACT_SOUNDS,
    IMPACTS,
    MAX_DURATION,
    MAX_EFFECTS,
    MIN_DURATION,
    PHRASES,
    PRESETS,
    SOUNDS,
    SOURCES,
    TEXT_STYLES,
)

HookTransitionMode = Literal["auto", "preset", "custom", "off"]


def _known(value: Optional[str], table: dict[str, Any], kind: str) -> Optional[str]:
    if value is not None and value not in table:
        raise ValueError(f"Unknown {kind}: {value}")
    return value


class HookTransitionConfig(BaseModel):
    """How the bridge between a clip's hook and the clip itself is built.

    ``auto`` picks a preset and bridge line suited to the clip; ``preset`` uses
    ``preset_id`` and ``custom`` builds from the parts. In both, any part given
    here overrides the preset's, so a user can start from a preset and tweak it.
    """

    mode: HookTransitionMode = "auto"
    preset_id: Optional[str] = None
    source: Optional[str] = None
    effects: Optional[list[str]] = None
    sound: Optional[str] = None
    impact: Optional[str] = None
    impact_sound: Optional[str] = None
    # A phrase id, "auto" to match the hook, or "none" for no bridge text.
    text_id: Optional[str] = None
    # Free text for the bridge card; wins over text_id.
    custom_text: Optional[str] = Field(default=None, max_length=60)
    text_style: Optional[str] = None
    duration: Optional[float] = Field(default=None, ge=MIN_DURATION, le=MAX_DURATION)

    @field_validator("preset_id")
    @classmethod
    def _preset(cls, value: Optional[str]) -> Optional[str]:
        return _known(value, PRESETS, "hook transition preset")

    @field_validator("source")
    @classmethod
    def _source(cls, value: Optional[str]) -> Optional[str]:
        return _known(value, SOURCES, "bridge source")

    @field_validator("sound")
    @classmethod
    def _sound(cls, value: Optional[str]) -> Optional[str]:
        return _known(value, SOUNDS, "bridge sound")

    @field_validator("impact")
    @classmethod
    def _impact(cls, value: Optional[str]) -> Optional[str]:
        return _known(value, IMPACTS, "impact")

    @field_validator("impact_sound")
    @classmethod
    def _impact_sound(cls, value: Optional[str]) -> Optional[str]:
        return None if value == "none" else _known(value, IMPACT_SOUNDS, "impact sound")

    @field_validator("text_style")
    @classmethod
    def _text_style(cls, value: Optional[str]) -> Optional[str]:
        return _known(value, TEXT_STYLES, "text style")

    @field_validator("text_id")
    @classmethod
    def _text_id(cls, value: Optional[str]) -> Optional[str]:
        if value in (None, "auto", "none"):
            return value
        return _known(value, PHRASES, "bridge phrase")

    @field_validator("custom_text")
    @classmethod
    def _custom_text(cls, value: Optional[str]) -> Optional[str]:
        text = " ".join((value or "").split())
        return text or None

    @field_validator("effects")
    @classmethod
    def _effects(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        effects = list(dict.fromkeys(value))
        for effect in effects:
            _known(effect, EFFECTS, "bridge effect")
        if len(effects) > MAX_EFFECTS:
            raise ValueError(f"At most {MAX_EFFECTS} bridge effects can be stacked")
        if len(FRAMING_EFFECTS.intersection(effects)) > 1:
            raise ValueError("Only one zoom, shake, spin, tilt or whip effect can be used at a time")
        return effects

    @model_validator(mode="after")
    def _mode_needs(self) -> "HookTransitionConfig":
        if self.mode == "preset" and not self.preset_id:
            raise ValueError("preset mode needs a preset_id")
        if self.mode == "custom" and not (self.source or self.preset_id):
            raise ValueError("custom mode needs a source (or a preset_id to start from)")
        return self


class HookTransitionCatalogResponse(BaseModel):
    sources: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    sounds: list[dict[str, Any]]
    impact_sounds: list[dict[str, Any]]
    impacts: list[dict[str, Any]]
    text_styles: list[dict[str, Any]]
    phrases: list[dict[str, Any]]
    groups: list[str]
    presets: list[dict[str, Any]]
    limits: dict[str, Any]
    default_preset: str


class HookTransitionApplied(BaseModel):
    """The concrete transition a render used (what Auto picked, when in Auto)."""

    preset_id: str
    source: str
    effects: list[str]
    sound: str
    impact: str
    impact_sound: Optional[str] = None
    text: Optional[str] = None
    text_style: str
    duration: float


class HookTransitionResolveResponse(BaseModel):
    clip_id: str
    # None when the clip has no hook to bridge from, or transitions are off.
    transition: Optional[HookTransitionApplied] = None
