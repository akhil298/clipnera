from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep, get_db
from auth.model import AuthProvider, User, UserAccount
from auth.schema import MessageResponse
from core.security import hash_password
from workspace.model import Workspace, WorkspaceMember, WorkspaceRole
from workspace.repository import WorkspaceRepository
from workspace.schema import (
    CreateWorkspaceRequest,
    WorkspaceResponse,
    WorkspaceMemberResponse,
    CreateMemberRequest,
    InviteMemberRequest,
    UpdateMemberRoleRequest,
)
from core.exceptions import CustomException
from subscription.dependencies import require_feature


async def get_workspace_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceRepository:
    return WorkspaceRepository(session)


WorkspaceRepoDep = Annotated[WorkspaceRepository, Depends(get_workspace_repo)]

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


async def _require_membership(repo: WorkspaceRepository, workspace_id: str, user_id: str) -> WorkspaceMember:
    """The caller's membership; 404 for non-members so workspace ids don't leak."""
    workspace = await repo.get_workspace(workspace_id)
    membership = await repo.get_membership(workspace_id, user_id) if workspace else None
    if not membership:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
    return membership


async def _require_owner(repo: WorkspaceRepository, workspace_id: str, user_id: str) -> None:
    """Only the owner may add, re-role or remove members."""
    membership = await _require_membership(repo, workspace_id, user_id)
    if membership.role != WorkspaceRole.OWNER:
        raise CustomException(
            message="Only the workspace owner can manage members", code="FORBIDDEN", status_code=403
        )


async def _get_editable_member(repo: WorkspaceRepository, workspace_id: str, member_id: str) -> WorkspaceMember:
    member = await repo.get_member(member_id)
    if not member or member.workspace_id != workspace_id:
        raise CustomException(message="Member not found", code="NOT_FOUND", status_code=404)
    if member.role == WorkspaceRole.OWNER:
        raise CustomException(message="The workspace owner cannot be changed", code="FORBIDDEN", status_code=403)
    return member


def _workspace_response(workspace: Workspace, role: str, member_count: int) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        owner_id=workspace.owner_id,
        role=role,
        member_count=member_count,
        created_at=workspace.created_at.isoformat(),
    )


def _member_response(member: WorkspaceMember, name: str | None = None) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        email=member.email,
        name=name,
        avatar_url=None,
        role=member.role.value,
        status=member.status.value,
        created_at=member.created_at.isoformat(),
    )


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    data: CreateWorkspaceRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    user_id = current_user["user_id"]
    user = (await repo.get_users_by_ids([user_id]))[user_id]
    workspace = await repo.create_workspace(data.name, user_id, user.email)
    return _workspace_response(workspace, WorkspaceRole.OWNER.value, 1)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    """The caller's workspaces. Anyone without one gets a personal workspace,
    so there is always somewhere to add team members."""
    user_id = current_user["user_id"]
    results = await repo.list_for_user(user_id)
    if not results:
        user = (await repo.get_users_by_ids([user_id]))[user_id]
        owner_name = user.full_name or user.email.split("@")[0]
        workspace = await repo.create_workspace(f"{owner_name}'s Workspace", user_id, user.email)
        return [_workspace_response(workspace, WorkspaceRole.OWNER.value, 1)]
    return [_workspace_response(ws, role.value, count) for ws, role, count in results]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    membership = await _require_membership(repo, workspace_id, current_user["user_id"])
    workspace = await repo.get_workspace(workspace_id)
    member_count = len(await repo.list_members(workspace_id))
    return _workspace_response(workspace, membership.role.value, member_count)


# Adding members is Pro; existing members can still be viewed, re-roled and removed.
@router.post(
    "/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=201,
    dependencies=[Depends(require_feature("team_members"))],
)
async def invite_member(
    workspace_id: str,
    data: InviteMemberRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    await _require_owner(repo, workspace_id, current_user["user_id"])
    member = await repo.add_member(
        workspace_id=workspace_id,
        email=data.email,
        role=WorkspaceRole(data.role),
        invited_by=current_user["user_id"],
    )
    return _member_response(member)


@router.post(
    "/{workspace_id}/members/create", response_model=WorkspaceMemberResponse, status_code=201,
    dependencies=[Depends(require_feature("team_members"))],
)
async def create_and_add_member(
    workspace_id: str,
    data: CreateMemberRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    """Create a regular user account and add it to the workspace.

    The account always gets the default ``user`` platform role; this route
    can never create a platform admin.
    """
    await _require_owner(repo, workspace_id, current_user["user_id"])
    if await repo.get_user_by_email(data.email):
        raise CustomException(
            message="A user with this email already exists. Use invite instead.",
            code="EMAIL_EXISTS",
            status_code=409,
        )

    hashed = await asyncio.to_thread(hash_password, data.password)
    session = repo._session
    user = User(email=data.email, full_name=data.full_name, username=data.email.split("@")[0])
    session.add(user)
    await session.flush()
    session.add(
        UserAccount(
            user_id=user.id,
            provider=AuthProvider.PASSWORD,
            provider_user_id=data.email,
            password_hash=hashed,
        )
    )

    member = await repo.add_member(
        workspace_id=workspace_id,
        email=data.email,
        role=WorkspaceRole(data.role),
        invited_by=current_user["user_id"],
        user_id=user.id,
    )
    return _member_response(member, data.full_name)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_members(
    workspace_id: str,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    await _require_membership(repo, workspace_id, current_user["user_id"])
    members = await repo.list_members(workspace_id)
    users = await repo.get_users_by_ids([m.user_id for m in members if m.user_id])
    return [
        _member_response(m, users[m.user_id].full_name if m.user_id in users else None)
        for m in members
    ]


@router.patch("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    workspace_id: str,
    member_id: str,
    data: UpdateMemberRoleRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    await _require_owner(repo, workspace_id, current_user["user_id"])
    member = await _get_editable_member(repo, workspace_id, member_id)
    member = await repo.update_member_role(member, WorkspaceRole(data.role))
    return _member_response(member)


@router.delete("/{workspace_id}/members/{member_id}", response_model=MessageResponse)
async def remove_member(
    workspace_id: str,
    member_id: str,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    await _require_owner(repo, workspace_id, current_user["user_id"])
    member = await _get_editable_member(repo, workspace_id, member_id)
    await repo.remove_member(member)
    return MessageResponse(message="Member removed")
