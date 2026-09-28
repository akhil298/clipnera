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

from dataclasses import dataclass, asdict
from typing import Any, Literal

from subscription.model import BillingPeriod, PlanSlug

# Boolean capabilities a route can require with ``require_feature``.
Feature = Literal[
    "remove_watermark",
    "pro_ai",
    "all_hook_transitions",
    "brand_kit_edit",
    "depth_captions",
    "batch_processing",
    "team_members",
    "social_scheduling",
    "custom_aspect_ratios",
]

# Actions metered per UTC day with ``check_limit``. None in a plan's limits
# means unlimited.
UsageKey = Literal["exports", "audio_enhancements", "reel_renders", "ai_shots", "auto_edits"]

# Hook transition modes every plan may use.
_FREE_HOOK_TRANSITION_MODES = frozenset({"auto", "off"})

# Credit minutes reset to the plan's allowance on this cycle, counted from the
# subscription start (paid) or the signup date (free). Unused minutes do not
# roll over.
CREDIT_CYCLE_DAYS = 30


@dataclass(frozen=True)
class PlanPrice:
    amount_inr: int
    days: int


# The one plan sold through UPI, and what each billing period costs. Payment
# amounts are always taken from here on the server, never from the client.
PURCHASABLE_PLAN = PlanSlug.PRO.value
PLAN_PRICES: dict[BillingPeriod, PlanPrice] = {
    BillingPeriod.MONTHLY: PlanPrice(amount_inr=699, days=30),
    BillingPeriod.YEARLY: PlanPrice(amount_inr=6990, days=365),
}


@dataclass(frozen=True)
class CreditPack:
    slug: str
    name: str
    credits: int
    amount_inr: int


# One-off credits sold through UPI, on any plan. Bought credits never expire and
# are spent after the plan's allowance. Each costs more per credit than Pro
# (₹699 for 600), so a subscription stays the better deal for regular use.
CREDIT_PACKS: dict[str, CreditPack] = {
    pack.slug: pack
    for pack in (
        CreditPack(slug="starter", name="Starter", credits=60, amount_inr=99),
        CreditPack(slug="creator", name="Creator", credits=200, amount_inr=299),
        CreditPack(slug="studio", name="Studio", credits=500, amount_inr=649),
    )
}

# Caption templates available without a paid plan. The rest of the catalogue
# (see subtitle_styling/templates.py) is a Pro feature.
FREE_CAPTION_STYLES: tuple[str, ...] = (
    # The default style for new clips, so it must be usable on every plan.
    "clean_dark",
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
    credit_minutes: int  # allowance per CREDIT_CYCLE_DAYS
    all_hook_transitions: bool  # False limits hook transitions to Auto
    brand_kit_edit: bool
    depth_captions: bool
    batch_processing: bool
    team_members: bool
    daily_limits: dict[str, int | None]
    # Connected publishing platforms (social/). Posts per UTC day count every
    # post created, whether published now or scheduled.
    social_max_accounts: int
    social_platforms: tuple[str, ...]
    social_scheduling: bool
    social_max_schedule_days: int
    social_posts_per_day: int
    # Picking output ratios at upload; without it the content category decides.
    custom_aspect_ratios: bool

    def allows_caption_style(self, style: str) -> bool:
        return self.caption_styles is None or style in self.caption_styles

    def allows_aspect_ratio(self, ratio: str) -> bool:
        return ratio in self.aspect_ratios

    def allows_hook_transition(self, mode: str | None) -> bool:
        """Free plans get Auto (or no transition); presets and custom mixes are paid."""
        return self.all_hook_transitions or (mode or "auto") in _FREE_HOOK_TRANSITION_MODES

    def features(self) -> dict[str, bool]:
        """Every boolean capability by name, for ``require_feature`` and the UI."""
        return {
            "remove_watermark": not self.watermark_forced,
            "pro_ai": self.pro_ai_provider,
            "all_hook_transitions": self.all_hook_transitions,
            "brand_kit_edit": self.brand_kit_edit,
            "depth_captions": self.depth_captions,
            "batch_processing": self.batch_processing,
            "team_members": self.team_members,
            "social_scheduling": self.social_scheduling,
            "custom_aspect_ratios": self.custom_aspect_ratios,
        }

    def allows(self, feature: Feature) -> bool:
        return self.features()[feature]

    def daily_limit(self, key: UsageKey) -> int | None:
        return self.daily_limits.get(key)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["aspect_ratios"] = list(self.aspect_ratios)
        data["social_platforms"] = list(self.social_platforms)
        data["caption_styles"] = (
            None if self.caption_styles is None else list(self.caption_styles)
        )
        data["features"] = self.features()
        return data


_ALL_ASPECT_RATIOS = ("9:16", "1:1", "4:5", "16:9")
# What every run renders unless a plan with custom_aspect_ratios picks otherwise.
DEFAULT_OUTPUT_ASPECT_RATIO = "9:16"

# Two hours. Long enough for a full podcast, short enough that one upload cannot
# monopolise the render queue.
_PRO_MAX_UPLOAD_SECONDS = 7200

# Capabilities every paid tier shares.
_PRO_FEATURES: dict[str, Any] = {
    "all_hook_transitions": True,
    "brand_kit_edit": True,
    "depth_captions": True,
    "batch_processing": True,
    "team_members": True,
    # Pro is unlimited where a run costs little; reels and AI shots have fair-use
    # caps so one account cannot spend a month's compute in a day.
    "daily_limits": {"exports": None, "audio_enhancements": None, "reel_renders": 20, "ai_shots": 10, "auto_edits": 15},
    "social_max_accounts": 4,
    "social_platforms": ("youtube", "tiktok", "instagram", "x"),
    "social_scheduling": True,
    "social_max_schedule_days": 30,
    "social_posts_per_day": 25,
    "custom_aspect_ratios": True,
}

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
        credit_minutes=20,
        all_hook_transitions=False,
        brand_kit_edit=False,
        depth_captions=False,
        batch_processing=False,
        team_members=False,
        daily_limits={"exports": 10, "audio_enhancements": 3, "reel_renders": 2, "ai_shots": 0, "auto_edits": 1},
        # X bills every post, so it is paid-only.
        social_max_accounts=1,
        social_platforms=("youtube", "tiktok", "instagram"),
        social_scheduling=False,
        social_max_schedule_days=0,
        social_posts_per_day=3,
        custom_aspect_ratios=False,
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
        credit_minutes=600,
        **_PRO_FEATURES,
    ),
    # No longer sold. Kept so existing Pro Plus subscribers keep these limits
    # until their current period ends; they renew as Pro.
    PlanSlug.PRO_PLUS.value: Entitlements(
        plan=PlanSlug.PRO_PLUS.value,
        aspect_ratios=_ALL_ASPECT_RATIOS,
        caption_styles=None,
        max_clips_per_video=50,
        watermark_forced=False,
        pro_ai_provider=True,
        priority_rendering=True,
        max_upload_duration_seconds=_PRO_MAX_UPLOAD_SECONDS,
        credit_minutes=1200,
        **_PRO_FEATURES,
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
