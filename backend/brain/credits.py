"""Credits for AI-editor plans: hold at Approve, commit per finished step, release the rest (TODO 14.2–14.3).

Prices are in AI credits (BLUEPRINT §11.4.2: plan 5 or 12 + 3 per step, critic round 7); the
user pays in Clipnera credits at ``AI_CREDIT_RATE`` AI credits each, rounded up. The hold is a
real deduction through the existing wallet (subscription.service), so the shown price is a
ceiling: steps that fail or are skipped come back with the release.
"""

from __future__ import annotations

import math

from core.config import get_settings
from subscription.service import SubscriptionService

MICRO_EDIT = 1
CRITIC_ROUND = 7
REFERENCE_TYPE = "edit_plan"


def to_clipnera(ai_credits: int) -> int:
    """Clipnera credits for an AI-credit price; anything above zero costs at least one."""
    if ai_credits <= 0:
        return 0
    return max(1, math.ceil(ai_credits / max(1, get_settings().AI_CREDIT_RATE)))


async def hold(subscriptions: SubscriptionService, user_id: str, plan_id: str, ai_credits: int) -> int:
    """Take the plan's ceiling now; returns the Clipnera credits held. Raises InsufficientCreditsError."""
    amount = to_clipnera(ai_credits)
    if amount:
        await subscriptions.deduct_credits(user_id, amount, "AI editor plan (held)", plan_id, REFERENCE_TYPE)
    return amount


async def release(subscriptions: SubscriptionService, user_id: str, plan_id: str, held: int, committed_ai: int) -> int:
    """Give back what the finished steps didn't use; returns the Clipnera credits finally charged."""
    charged = min(held, to_clipnera(committed_ai))
    if held - charged > 0:
        await subscriptions.refund_credits(user_id, held - charged, "AI editor plan (unused hold returned)", plan_id,
                                           REFERENCE_TYPE)
    return charged
