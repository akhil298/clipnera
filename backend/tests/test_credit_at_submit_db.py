"""A run asked for with a YouTube download is charged when it is asked for,
not minutes later when the download finishes, and given back if it never runs."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import pipeline.service as pipeline_service
from billing_db import balance, maker, new_user, requires_db  # noqa: F401  maker is a fixture
from clip.model import ProjectStatus
from clip.repository import ClipRepository
from core.exceptions import CustomException
from pipeline.model import PipelineStepType
from pipeline.schema import PipelineStartRequest

pytestmark = requires_db

RUN = PipelineStartRequest(output_aspect_ratios=["9:16"])


@pytest.fixture(autouse=True)
def _sessions(monkeypatch, maker):
    monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", maker)


async def _project(maker, user_id: str) -> str:
    async with maker() as session:
        project = await ClipRepository(session).create_project(
            user_id=user_id, title="Talk", source_type="youtube", status=ProjectStatus.PROCESSING
        )
        return project.id


async def _start(maker, user_id: str, project_id: str, duration_seconds: int):
    """What /pipeline/start does once the download is stored: price and charge."""
    async with maker() as session:
        project = SimpleNamespace(id=project_id, duration_seconds=duration_seconds)
        plan = await pipeline_service.PipelineRunService._plan_run(session, project, user_id, RUN.body(), resume=False)
        await pipeline_service._pipeline_repository(session).create_pipeline(project_id, [PipelineStepType.TRANSCRIPTION])
        return plan


@pytest.mark.asyncio
async def test_the_balance_drops_when_the_run_is_asked_for(maker):
    user_id = await new_user(maker, "a@example.com")
    start = await balance(maker, user_id)
    project_id = await _project(maker, user_id)

    charged = await pipeline_service.prepay_run(project_id, user_id, 120, RUN)

    assert charged == 4
    assert await balance(maker, user_id) == start - 4


@pytest.mark.asyncio
async def test_the_start_only_settles_the_difference_the_real_length_makes(maker):
    user_id = await new_user(maker, "b@example.com")
    start = await balance(maker, user_id)
    longer = await _project(maker, user_id)
    shorter = await _project(maker, user_id)

    await pipeline_service.prepay_run(longer, user_id, 120, RUN)
    plan = await _start(maker, user_id, longer, 180)  # 6 credits, 4 already paid
    assert plan.credit_cost == 6
    assert await balance(maker, user_id) == start - 6

    await pipeline_service.prepay_run(shorter, user_id, 120, RUN)
    await _start(maker, user_id, shorter, 60)  # 2 credits, 4 already paid
    assert await balance(maker, user_id) == start - 6 - 2

    # A failed run refunds everything it cost, up front part included.
    await plan.refund()
    assert await balance(maker, user_id) == start - 2


@pytest.mark.asyncio
async def test_a_run_that_never_happens_is_refunded_once(maker):
    user_id = await new_user(maker, "c@example.com")
    start = await balance(maker, user_id)
    project_id = await _project(maker, user_id)

    await pipeline_service.prepay_run(project_id, user_id, 120, RUN)
    await pipeline_service.release_prepaid(project_id, user_id)
    await pipeline_service.release_prepaid(project_id, user_id)

    assert await balance(maker, user_id) == start


@pytest.mark.asyncio
async def test_nothing_is_released_once_the_run_exists(maker):
    user_id = await new_user(maker, "d@example.com")
    start = await balance(maker, user_id)
    project_id = await _project(maker, user_id)

    await pipeline_service.prepay_run(project_id, user_id, 120, RUN)
    await _start(maker, user_id, project_id, 120)
    # Deleting a processed project must not hand its credits back.
    await pipeline_service.release_prepaid(project_id, user_id)

    assert await balance(maker, user_id) == start - 4


@pytest.mark.asyncio
async def test_two_requests_at_once_cannot_spend_the_same_credits(maker):
    user_id = await new_user(maker, "e@example.com")
    start = await balance(maker, user_id)
    seconds = start * 30  # each run costs the whole balance
    projects = [await _project(maker, user_id) for _ in range(2)]

    results = await asyncio.gather(
        *(pipeline_service.prepay_run(p, user_id, seconds, RUN) for p in projects), return_exceptions=True
    )

    refused = [r for r in results if isinstance(r, CustomException)]
    assert len(refused) == 1 and refused[0].code == "INSUFFICIENT_CREDITS"
    assert await balance(maker, user_id) == 0


@pytest.mark.asyncio
async def test_a_video_longer_than_the_plan_allows_is_refused_before_any_charge(maker):
    user_id = await new_user(maker, "f@example.com")
    start = await balance(maker, user_id)
    project_id = await _project(maker, user_id)

    with pytest.raises(CustomException) as refused:
        await pipeline_service.prepay_run(project_id, user_id, 10 * 3600, RUN)

    assert refused.value.code == "DURATION_NOT_ENTITLED"
    assert await balance(maker, user_id) == start
