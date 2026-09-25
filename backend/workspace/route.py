from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep, get_db
from auth.schema import MessageResponse
from workspace.repository import WorkspaceRepository
from workspace.schema import (
    CreateWorkspaceRequest,
    WorkspaceResponse,
    WorkspaceMemberResponse,
    CreateMemberRequest,
    InviteMemberRequest,
    UpdateMemberRoleRequest,
)
from workspace.service import WorkspaceService
from subscription.dependencies import require_feature


async def get_workspace_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceService:
    return WorkspaceService(WorkspaceRepository(session))


WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(data: CreateWorkspaceRequest, current_user: CurrentUserDep, service: WorkspaceServiceDep):
    return await service.create_workspace(current_user["user_id"], data)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(current_user: CurrentUserDep, service: WorkspaceServiceDep):
    """The caller's workspaces. Anyone without one gets a personal workspace,
    so there is always somewhere to add team members."""
    return await service.list_workspaces(current_user["user_id"])


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, current_user: CurrentUserDep, service: WorkspaceServiceDep):
    return await service.get_workspace(workspace_id, current_user["user_id"])


# Adding members is Pro; existing members can still be viewed, re-roled and removed.
@router.post(
    "/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=201,
    dependencies=[Depends(require_feature("team_members"))],
)
async def invite_member(
    workspace_id: str, data: InviteMemberRequest, current_user: CurrentUserDep, service: WorkspaceServiceDep
):
    return await service.invite_member(workspace_id, current_user["user_id"], data)


@router.post(
    "/{workspace_id}/members/create", response_model=WorkspaceMemberResponse, status_code=201,
    dependencies=[Depends(require_feature("team_members"))],
)
async def create_and_add_member(
    workspace_id: str, data: CreateMemberRequest, current_user: CurrentUserDep, service: WorkspaceServiceDep
):
    """Create a regular user account and add it to the workspace.

    The account always gets the default ``user`` platform role; this route
    can never create a platform admin.
    """
    return await service.create_member(workspace_id, current_user["user_id"], data)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_members(workspace_id: str, current_user: CurrentUserDep, service: WorkspaceServiceDep):
    return await service.list_members(workspace_id, current_user["user_id"])


@router.patch("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    workspace_id: str,
    member_id: str,
    data: UpdateMemberRoleRequest,
    current_user: CurrentUserDep,
    service: WorkspaceServiceDep,
):
    return await service.update_member_role(workspace_id, member_id, current_user["user_id"], data)


@router.delete("/{workspace_id}/members/{member_id}", response_model=MessageResponse)
async def remove_member(
    workspace_id: str, member_id: str, current_user: CurrentUserDep, service: WorkspaceServiceDep
):
    await service.remove_member(workspace_id, member_id, current_user["user_id"])
    return MessageResponse(message="Member removed")
