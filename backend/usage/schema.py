from __future__ import annotations

from pydantic import BaseModel


class StepUsage(BaseModel):
    step: str
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    audio_seconds: float
    cost_usd: float


class ProjectUsage(BaseModel):
    project_id: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    audio_seconds: float
    cost_usd: float
    by_step: list[StepUsage]


class DailyUsage(BaseModel):
    day: str
    calls: int
    cost_usd: float


class ModelUsage(BaseModel):
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class TopProjectUsage(BaseModel):
    project_id: str
    user_id: str | None
    calls: int
    cost_usd: float


class CostPerMinute(BaseModel):
    """Measured AI spend per minute of source video, to price credits against."""

    tier: str
    projects: int
    source_minutes: float
    cost_per_source_minute_usd: float


class AdminUsageSummary(BaseModel):
    days: int
    calls: int
    cost_usd: float
    cost_per_minute: list[CostPerMinute]
    by_day: list[DailyUsage]
    by_model: list[ModelUsage]
    top_projects: list[TopProjectUsage]
