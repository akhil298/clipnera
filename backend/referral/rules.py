"""The referral program's rules and the small pure helpers around them."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta

CODE_PREFIX = "CLIP-"
# No 0/O, 1/I/L: codes are read aloud and typed from screenshots.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 5

# Months for the referral cap are counted in India time, where the business runs.
CAP_TIMEZONE_OFFSET = timedelta(hours=5, minutes=30)
# A sign-up from an IP the referrer used this recently is held for review.
SHARED_IP_LOOKBACK = timedelta(days=30)
# How long before a deadline the referred user is reminded.
REMINDER_BEFORE = timedelta(hours=12)
# A run started inside the video window still counts if it finishes this long
# after the window; longer than that it is treated as stuck.
RUN_FINISH_GRACE = timedelta(hours=24)

GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})


@dataclass(frozen=True)
class Rules:
    """What a referral earns and by when. Admins change the stored copy; each
    referral keeps the copy that applied when it began."""

    referee_pro_credits: int = 150
    referrer_pro_credits: int = 150
    referrer_video_credits: int = 150
    bonus_expiry_days: int = 30
    pro_window_hours: int = 48
    video_window_hours: int = 48
    monthly_cap: int = 20
    min_video_seconds: int = 60
    approval_wait_days: int = 7

    @classmethod
    def from_dict(cls, data: dict) -> "Rules":
        """Rules from a stored snapshot; anything it lacks keeps its default."""
        names = {f.name for f in fields(cls)}
        return cls(**{key: int(value) for key, value in data.items() if key in names})

    @classmethod
    def from_row(cls, row) -> "Rules":
        return cls(**{f.name: getattr(row, f.name) for f in fields(cls)})

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def pro_window(self) -> timedelta:
        return timedelta(hours=self.pro_window_hours)

    @property
    def video_window(self) -> timedelta:
        return timedelta(hours=self.video_window_hours)

    @property
    def approval_wait(self) -> timedelta:
        return timedelta(days=self.approval_wait_days)


def new_code() -> str:
    return CODE_PREFIX + "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: str) -> str:
    """``clip-7k3q9``, `` 7K3Q9 `` and ``CLIP-7K3Q9`` are the same code."""
    code = "".join(raw.split()).upper()
    return code if code.startswith(CODE_PREFIX) else CODE_PREFIX + code


def normalize_email(email: str) -> str:
    """The mailbox an address delivers to: Gmail ignores dots and anything after
    "+", so ``a.b+x@gmail.com`` and ``ab@gmail.com`` are the same person."""
    local, _, domain = email.strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def email_hash(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode()).hexdigest()


def display_name(full_name: str | None, email: str) -> str:
    """First name and last initial ("Ravi K."), never the full name."""
    parts = (full_name or "").split()
    if not parts:
        return email.split("@", 1)[0][:2] + "***"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0].upper()}."


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"


def month_start_utc(now: datetime) -> datetime:
    """Start of the current India-time month, as a naive UTC time."""
    local = now + CAP_TIMEZONE_OFFSET
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - CAP_TIMEZONE_OFFSET
