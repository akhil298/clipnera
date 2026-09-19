"""What each plan is allowed to do.

Single source of truth for tier capabilities. The API serves this table to the
frontend (so the UI can disable what a user cannot use and say why) and the
pipeline routes enforce it (so hiding a control in the UI is not the only thing
standing between a free user and a paid feature).

Adding a capability means adding a field here and a check at the point of use --
never an inline ``plan == "free"`` test, which is how gating drifts out of sync
between the two sides.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from subscription.model import PlanSlug

# Caption templates available without a paid plan. The rest of the catalogue
# (see subtitle_styling/templates.py) is a Pro feature.
FREE_CAPTION_STYLES: tuple[str, ...] = (
    "default",
    "hormozi",
    "mrbeast",
    "tiktok",
    "bold_captions",
)


@dataclass(frozen=True)
class Entitlements:
    """The capability set granted by a plan."""

    plan: str
    aspect_ratios: tuple[str, ...]
    caption_styles: tuple[str, ...] | None  # None means "every style"
    max_clips_per_video: int
    watermark_forced: bool
    pro_ai_provider: bool
    priority_rendering: bool
    max_upload_duration_seconds: int

    def allows_caption_style(self, style: str) -> bool:
        return self.caption_styles is None or style in self.caption_styles

    def allows_aspect_ratio(self, ratio: str) -> bool:
        return ratio in self.aspect_ratios

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["aspect_ratios"] = list(self.aspect_ratios)
        data["caption_styles"] = (
            None if self.caption_styles is None else list(self.caption_styles)
        )
        return data


_ALL_ASPECT_RATIOS = ("9:16", "1:1", "4:5", "16:9")

# Two hours. Long enough for a full podcast, short enough that one upload cannot
# monopolise the render queue.
_PRO_MAX_UPLOAD_SECONDS = 7200

ENTITLEMENTS: dict[str, Entitlements] = {
    PlanSlug.FREE.value: Entitlements(
        plan=PlanSlug.FREE.value,
        aspect_ratios=("9:16",),
        caption_styles=FREE_CAPTION_STYLES,
        max_clips_per_video=5,
        watermark_forced=True,
        pro_ai_provider=False,
        priority_rendering=False,
        max_upload_duration_seconds=1800,
    ),
    PlanSlug.PRO.value: Entitlements(
        plan=PlanSlug.PRO.value,
        aspect_ratios=_ALL_ASPECT_RATIOS,
        caption_styles=None,
        max_clips_per_video=20,
        watermark_forced=False,
        pro_ai_provider=True,
        priority_rendering=False,
        max_upload_duration_seconds=_PRO_MAX_UPLOAD_SECONDS,
    ),
    PlanSlug.PRO_PLUS.value: Entitlements(
        plan=PlanSlug.PRO_PLUS.value,
        aspect_ratios=_ALL_ASPECT_RATIOS,
        caption_styles=None,
        max_clips_per_video=50,
        watermark_forced=False,
        pro_ai_provider=True,
        priority_rendering=True,
        max_upload_duration_seconds=_PRO_MAX_UPLOAD_SECONDS,
    ),
}


def entitlements_for(plan_slug: str | None) -> Entitlements:
    """Capabilities for a plan, defaulting to Free.

    An unknown or missing plan resolves to Free rather than raising: a user
    whose subscription row is broken should get the restricted experience, not
    an error page, and certainly not the paid one.
    """
    if not plan_slug:
        return ENTITLEMENTS[PlanSlug.FREE.value]
    slug = getattr(plan_slug, "value", plan_slug)
    return ENTITLEMENTS.get(str(slug), ENTITLEMENTS[PlanSlug.FREE.value])
