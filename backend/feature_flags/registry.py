"""Every runtime feature switch an admin can flip.

A flag must be declared here before it can be read or set, so a typo fails
loudly instead of silently reading as "off". Flags default to off: a new
feature ships dark and is turned on from the admin panel. A child flag only
counts as on while its parent is on too.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlagDefinition:
    key: str
    label: str
    description: str
    parent: str | None = None


SOCIAL_PUBLISHING = "social_publishing"


def social_platform_flag(platform: str) -> str:
    return f"{SOCIAL_PUBLISHING}.{platform}"


_DEFINITIONS = (
    FlagDefinition(
        SOCIAL_PUBLISHING,
        "Connected publishing platforms",
        "Users can connect social accounts and publish or schedule clips. Turning this off "
        "pauses publishing; disconnects and platform deletion requests keep working.",
    ),
    FlagDefinition(
        social_platform_flag("youtube"), "YouTube Shorts", "Connect and publish to YouTube.", SOCIAL_PUBLISHING
    ),
    FlagDefinition(
        social_platform_flag("tiktok"), "TikTok", "Connect and publish to TikTok.", SOCIAL_PUBLISHING
    ),
    FlagDefinition(
        social_platform_flag("instagram"), "Instagram Reels", "Connect and publish to Instagram.", SOCIAL_PUBLISHING
    ),
    FlagDefinition(
        social_platform_flag("x"), "X", "Connect and publish to X. Every post is billed by X.", SOCIAL_PUBLISHING
    ),
)

FLAGS: dict[str, FlagDefinition] = {flag.key: flag for flag in _DEFINITIONS}
