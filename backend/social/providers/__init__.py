from __future__ import annotations

from social.model import SocialPlatform
from social.providers.base import PlatformProvider
from social.providers.instagram import InstagramProvider
from social.providers.tiktok import TikTokProvider
from social.providers.x import XProvider
from social.providers.youtube import YouTubeProvider

_PROVIDERS: dict[SocialPlatform, type[PlatformProvider]] = {
    SocialPlatform.YOUTUBE: YouTubeProvider,
    SocialPlatform.TIKTOK: TikTokProvider,
    SocialPlatform.INSTAGRAM: InstagramProvider,
    SocialPlatform.X: XProvider,
}


def get_provider(platform: SocialPlatform | str) -> PlatformProvider:
    """A fresh provider for one unit of work; it owns its HTTP client until closed."""
    return _PROVIDERS[SocialPlatform(platform)]()
