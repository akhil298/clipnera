"""Request and response models for /social. None of them carry token fields."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, PlainSerializer, field_validator

Platform = Literal["youtube", "tiktok", "instagram", "x"]
AccountStatusName = Literal["active", "needs_reconnect", "disconnecting", "disconnected"]
PostStatusName = Literal["scheduled", "publishing", "published", "failed", "cancelled"]


def _as_utc(value: datetime) -> str:
    """Stored times are naive UTC; send them with an explicit offset."""
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_as_utc, return_type=str)]


# -- accounts ------------------------------------------------------------------


class PlatformInfo(BaseModel):
    platform: Platform
    label: str
    # Turned on by an admin (feature flags) and configured with app credentials.
    available: bool
    # The caller's plan includes this platform.
    allowed_by_plan: bool
    caption_max_chars: int
    max_duration_seconds: float
    # Shown while Clipnera's app awaits the platform's review.
    pending_review_note: Optional[str] = None


class ConnectedAccountResponse(BaseModel):
    id: str
    platform: Platform
    handle: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    follower_count: Optional[int] = None
    follower_count_updated_at: Optional[UtcDateTime] = None
    status: AccountStatusName
    status_reason: Optional[str] = None
    connected_at: UtcDateTime


class ConnectionsResponse(BaseModel):
    platforms: List[PlatformInfo]
    accounts: List[ConnectedAccountResponse]
    max_accounts: int
    can_schedule: bool
    max_schedule_days: int
    posts_per_day: int


class ConnectStartResponse(BaseModel):
    authorize_url: str


class ConnectCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=200)


class DisconnectPreviewResponse(BaseModel):
    account_id: str
    pending_posts: int


class TikTokCreatorInfoResponse(BaseModel):
    nickname: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    privacy_level_options: List[str]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: Optional[int] = None


# -- posts ---------------------------------------------------------------------


class PostTarget(BaseModel):
    account_id: str = Field(min_length=1, max_length=36)
    caption: str = Field(default="", max_length=5000)
    # Platform-specific settings, validated by the platform's provider.
    options: Dict[str, Any] = Field(default_factory=dict)


class CreatePostsRequest(BaseModel):
    clip_id: str = Field(min_length=1, max_length=36)
    targets: List[PostTarget] = Field(min_length=1, max_length=8)
    # Omit to publish now. Must carry a timezone offset.
    scheduled_at: Optional[datetime] = None
    # Generated once per submit by the client; a retried submit returns the same posts.
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("scheduled_at")
    @classmethod
    def _require_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return value

    @field_validator("targets")
    @classmethod
    def _distinct_accounts(cls, targets: list[PostTarget]) -> list[PostTarget]:
        if len({t.account_id for t in targets}) != len(targets):
            raise ValueError("each account can appear only once")
        return targets


class PostResponse(BaseModel):
    id: str
    publish_group_id: str
    account_id: str
    platform: Platform
    account_handle: Optional[str] = None
    clip_id: str
    clip_title: str
    caption: str
    platform_options: Dict[str, Any]
    scheduled_at: UtcDateTime
    status: PostStatusName
    post_url: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int
    published_at: Optional[UtcDateTime] = None
    created_at: UtcDateTime


class PostListResponse(BaseModel):
    posts: List[PostResponse]


# -- admin ---------------------------------------------------------------------


class AdminPlatformStats(BaseModel):
    platform: Platform
    accounts: Dict[str, int]
    # Posts updated in the window, by status.
    posts: Dict[str, int]
    success_rate: Optional[float] = None


class AdminFailure(BaseModel):
    post_id: str
    platform: Platform
    account_handle: Optional[str] = None
    user_email: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int
    failed_at: UtcDateTime


class AdminSocialOverviewResponse(BaseModel):
    window_days: int
    platforms: List[AdminPlatformStats]
    quota: Dict[str, Dict[str, float]]
    recent_failures: List[AdminFailure]


class AdminAccountResponse(BaseModel):
    id: str
    platform: Platform
    handle: Optional[str] = None
    display_name: Optional[str] = None
    follower_count: Optional[int] = None
    status: AccountStatusName
    status_reason: Optional[str] = None
    user_id: str
    user_email: str
    connected_at: UtcDateTime


class AdminAccountListResponse(BaseModel):
    accounts: List[AdminAccountResponse]


# -- webhooks ------------------------------------------------------------------


class DeletionStatusResponse(BaseModel):
    confirmation_code: str
    platform: Platform
    completed: bool
    accounts_deleted: int
    requested_at: UtcDateTime
