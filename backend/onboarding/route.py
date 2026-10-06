from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from core.database import get_db
from core.responses import ApiResponse, ok
from onboarding.schema import OnboardingRequest, OnboardingResponse, OnboardingStatusResponse
from onboarding.service import OnboardingService

onboarding = APIRouter(prefix="/onboarding", tags=["onboarding"])


def get_onboarding_service(session: Annotated[AsyncSession, Depends(get_db)]) -> OnboardingService:
    return OnboardingService(session)


OnboardingServiceDep = Annotated[OnboardingService, Depends(get_onboarding_service)]


@onboarding.get("", response_model=ApiResponse[OnboardingStatusResponse])
async def get_onboarding(user: CurrentUserDep, service: OnboardingServiceDep):
    return ok(await service.status(user["user_id"]))


@onboarding.post("", response_model=ApiResponse[OnboardingResponse])
async def complete_onboarding(body: OnboardingRequest, user: CurrentUserDep, service: OnboardingServiceDep):
    return ok(await service.complete(user["user_id"], body), message="Welcome to Clipnera")
