"""The motion library as agent tools: find a motion asset or an editing asset, or learn there is none."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_runtime.tools import AgentTool
from motion_library.catalog import find_assets
from motion_library.editing_assets import find_editing_assets


class FindMotionAssetInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="What the moment needs, in a few words: 'money rain', 'warm glow', 'flash on the cut'.")
    kind: Literal["animated_emoji", "overlay", "transition", "motion_graphic", "green_screen"] | None = Field(
        None, description="Limit the search to one kind of asset.")
    limit: int = Field(5, ge=1, le=10)


async def _find(_: Any, search: FindMotionAssetInput) -> dict[str, Any]:
    assets = find_assets(search.query, search.kind, search.limit)
    if not assets:
        wanted = search.kind.replace("_", " ") if search.kind else "asset"
        return {
            "found": False,
            "message": f"No {wanted} in the motion library matches '{search.query}'. "
                       "Do not invent one; make the edit without it.",
        }
    return {"found": True, "assets": [asset.summary() for asset in assets]}


FIND_MOTION_ASSET = AgentTool(
    "find_motion_asset",
    "Search the local motion library (animated emoji, overlays, transitions, motion graphics, green screen) "
    "for an asset to add to the edit. Returns the matches, or found=false when the library has nothing "
    "suitable. Use only ids this tool returns.",
    FindMotionAssetInput, _find,
)



class FindEditingAssetInput(BaseModel):
    collection: Literal["hook_collection", "music_collection", "effect_collection", "sfx_collection"] = Field(
        ..., description="Hooks (opening recipes), music (mood, energy, bpm, beats), effects (techniques and "
                         "how to do them) or sound effects (our own sound ids, with where reels used them).")
    query: str = Field(..., min_length=1, max_length=200, description="What the edit needs: 'car title reveal', 'dramatic phonk', 'match cut', 'whoosh on cut'.")
    limit: int = Field(5, ge=1, le=10)


async def _find_editing(_: Any, search: FindEditingAssetInput) -> dict[str, Any]:
    assets = find_editing_assets(search.collection, search.query, search.limit)
    if not assets:
        return {"found": False, "message": f"Nothing in the {search.collection.replace('_', ' ')} matches "
                                           f"'{search.query}'. Do not invent one; make the edit without it."}
    return {
        "found": True, "assets": assets,
        "rule": "Clips whose license.commercial_ok is false must not go into an export: use the template, "
                "the technique, the sound id, or a licensed track with the same mood, energy and bpm.",
    }


FIND_EDITING_ASSET = AgentTool(
    "find_editing_asset",
    "Search the editing assets collected from viral reels: hooks with their templates, music with tempo and "
    "beats, effects with how to reproduce them, and sound effects. Returns matches, or found=false.",
    FindEditingAssetInput, _find_editing,
)
