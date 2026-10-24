"""Today's USD→INR rate, so dollar prices can be charged in rupees over UPI."""

from __future__ import annotations

import math
import time

import httpx

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

# European Central Bank reference rates; no key needed, updated once a working day.
RATE_URL = "https://api.frankfurter.app/latest?from=USD&to=INR"
RATE_TTL_SECONDS = 6 * 3600
# After a failed fetch, retry this soon rather than holding a fallback for hours.
RETRY_AFTER_SECONDS = 600

_cached: tuple[float, float] | None = None  # (rate, monotonic expiry)


async def usd_inr_rate() -> float:
    """Rupees per dollar: today's rate, the last good one if the source is down,
    else ``USD_INR_FALLBACK_RATE``."""
    global _cached
    if _cached and time.monotonic() < _cached[1]:
        return _cached[0]
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            response = await client.get(RATE_URL)
            response.raise_for_status()
            rate = float(response.json()["rates"]["INR"])
        _cached = (rate, time.monotonic() + RATE_TTL_SECONDS)
        return rate
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        rate = _cached[0] if _cached else get_settings().USD_INR_FALLBACK_RATE
        log.warning(f"USD→INR rate fetch failed ({exc}); using {rate}")
        _cached = (rate, time.monotonic() + RETRY_AFTER_SECONDS)
        return rate


def to_inr(amount_usd: float, rate: float) -> int:
    """A dollar price in whole rupees, rounded up so the charge never falls short."""
    return math.ceil(amount_usd * rate)
