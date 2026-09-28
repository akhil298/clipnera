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
VIDEO_UPLOAD = "video_upload"
BROLL_STUDIO = "broll_studio"
BROLL_CUTAWAYS = f"{BROLL_STUDIO}.cutaways"
BROLL_REELS = f"{BROLL_STUDIO}.reels"
BROLL_AI_SHOTS = f"{BROLL_STUDIO}.ai_shots"
REEL_EDITOR = f"{BROLL_REELS}.footage"
REEL_EDITOR_OPUS = f"{REEL_EDITOR}.opus_director"


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
    FlagDefinition(
        VIDEO_UPLOAD,
        "Video upload",
        "Users can upload a video file from their device instead of pasting a YouTube link.",
    ),
    FlagDefinition(
        BROLL_STUDIO,
        "B-Roll Studio",
        "Main switch for B-roll features. The admin B-roll library stays available so it can be filled "
        "before launch.",
    ),
    FlagDefinition(
        BROLL_CUTAWAYS,
        "B-roll cutaways on clips",
        "The AI adds stock cutaways to generated clips (5 credits per clip that gets them); users can swap "
        "or remove them in the editor. Clips already planned keep their B-roll when this is turned off.",
        BROLL_STUDIO,
    ),
    FlagDefinition(
        BROLL_REELS,
        "Reels from images",
        "Users build a reel from their photos and a script or topic.",
        BROLL_STUDIO,
    ),
    FlagDefinition(
        BROLL_AI_SHOTS,
        "AI-generated shots (Pro)",
        "Pro users can generate a scene or cutaway with Veo (120 credits). Needs Veo quota on the Gemini key.",
        BROLL_STUDIO,
    ),
    FlagDefinition(
        REEL_EDITOR,
        "Reels from raw footage",
        "Users upload raw videos, photos, an optional script and voiceover; the AI plans and renders a finished reel.",
        BROLL_REELS,
    ),
    FlagDefinition(
        REEL_EDITOR_OPUS,
        "Opus director for Pro footage reels",
        "Pro footage reels are planned by Claude Opus 5.5 instead of Sonnet 5. Opus costs more, so these reels "
        "cost 1.5x the credits while this is on.",
        REEL_EDITOR,
    ),
)

FLAGS: dict[str, FlagDefinition] = {flag.key: flag for flag in _DEFINITIONS}
