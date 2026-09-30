"""What each platform's intro looks like: its primary colour and its buttons.

The intro copies the platform's own controls, so a viewer recognises exactly
what to tap: YouTube's red Subscribe, TikTok's pink Follow, and so on. Colours
are the platforms' published brand colours; ``other`` (a website, a podcast)
takes the creator's brand-kit colour instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Platform = Literal["youtube", "tiktok", "instagram", "twitch", "x", "facebook", "kick", "linkedin", "other"]
Icon = Literal["thumb", "heart"]


@dataclass(frozen=True)
class Look:
    # The main call to action, before and after the cursor clicks it.
    action: str
    done: str
    # Background and label colour of the main button before the click.
    accent: str
    accent_text: str
    # The like control next to it; None shows the main button alone.
    like_icon: Icon | None
    like_label: str
    # Colour the like icon turns when clicked; None keeps the text colour.
    liked_color: str | None


PLATFORM_LOOKS: dict[str, Look] = {
    "youtube": Look("Subscribe", "Subscribed", "#FF0000", "#FFFFFF", "thumb", "Like", None),
    "tiktok": Look("Follow", "Following", "#FE2C55", "#FFFFFF", "heart", "Like", "#FE2C55"),
    "instagram": Look("Follow", "Following", "#0095F6", "#FFFFFF", "heart", "Like", "#FF3040"),
    "twitch": Look("Follow", "Following", "#9146FF", "#FFFFFF", None, "", None),
    "x": Look("Follow", "Following", "#0F1419", "#FFFFFF", "heart", "Like", "#F91880"),
    "facebook": Look("Follow", "Following", "#0866FF", "#FFFFFF", "thumb", "Like", "#0866FF"),
    "kick": Look("Follow", "Following", "#53FC18", "#0B0E0F", None, "", None),
    "linkedin": Look("Follow", "Following", "#0A66C2", "#FFFFFF", "thumb", "Like", "#0A66C2"),
    "other": Look("Follow", "Following", "#F59E0B", "#0B0B0B", "heart", "Like", "#F43F5E"),
}

PLATFORM_NAMES: dict[str, str] = {
    "youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram", "twitch": "Twitch", "x": "X",
    "facebook": "Facebook", "kick": "Kick", "linkedin": "LinkedIn", "other": "the web",
}


def look_for(platform: str, brand_color: str | None = None) -> Look:
    """The platform's look; ``other`` wears the creator's brand colour when they set one."""
    look = PLATFORM_LOOKS.get(platform, PLATFORM_LOOKS["other"])
    if platform == "other" and brand_color:
        return Look(look.action, look.done, brand_color, _readable_on(brand_color), look.like_icon,
                    look.like_label, brand_color)
    return look


def _readable_on(hex_color: str) -> str:
    """Black or white, whichever reads better on ``hex_color``."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#0B0B0B" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#FFFFFF"
