"""What a footage reel costs the user, and why.

Target: 40-50% margin on what a Pro user pays, after tax, on the model and
compute a reel really uses, while keeping enough reels in the monthly
allowance that nobody runs out mid-month and leaves.

One credit on Pro is ₹699 / 600 = ₹1.165, or about ₹0.99 (~$0.011) after 18%
GST. A typical reel (5 min of raw footage in, 45 s out) costs about:

* Sonnet 5 director: ~$0.11 of API calls (transcription, contact-sheet
  captions, director, copy), plus ~30% for re-plans, chat edits and failed
  runs we refund, so ~$0.15. It is charged 6 + 15 + 5 = 26 credits, ~$0.29:
  a ~48% margin.
* Opus 5.5 director (admin flag): ~$0.19, ~$0.25 with overhead. The 1.5x
  multiplier makes it 39 credits, ~$0.44: a ~43% margin.

Compute runs inside the free tier, so it is not in the sums. At 26 credits a
Pro user gets ~23 reels a month, and Free's 20 credits cover one 30 s reel
from 3 minutes of footage. Plans and previews are free, re-renders after
edits cost a quarter, and failed renders are refunded, so users only pay for
a result they chose.
"""

from __future__ import annotations

import math

from core.config import get_settings


def reel_credits(output_seconds: float, raw_seconds: float, opus: bool = False) -> int:
    settings = get_settings()
    credits = (
        settings.EDIT_BASE_CREDITS
        + math.ceil(max(0.0, output_seconds) / settings.EDIT_OUTPUT_SECONDS_PER_CREDIT)
        + math.ceil(max(0.0, raw_seconds) / 60)
    )
    return math.ceil(credits * settings.EDIT_OPUS_CREDIT_MULTIPLIER) if opus else credits


def rerender_credits(full_price: int) -> int:
    """A render of an already-rendered reel after edits: no AI runs again."""
    return max(1, math.ceil(full_price * get_settings().EDIT_RERENDER_SHARE))
