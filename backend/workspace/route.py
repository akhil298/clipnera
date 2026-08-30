from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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
from core.exceptions import CustomException


async def get_workspace_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceRepository:
    return WorkspaceRepository(session)


WorkspaceRepoDep = Annotated[WorkspaceRepository, Depends(get_workspace_repo)]

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    data: CreateWorkspaceRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    workspace = await repo.create_workspace(data.name, current_user["user_id"], "")
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        owner_id=workspace.owner_id,
        role="owner",
        member_count=1,
        created_at=workspace.created_at.isoformat(),
    )


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    results = await repo.list_for_user(current_user["user_id"])
    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            owner_id=ws.owner_id,
            role=role,
            member_count=count,
            created_at=ws.created_at.isoformat(),
        )
        for ws, role, count in results
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    workspace = await repo.get_workspace(workspace_id)
    if not workspace:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        owner_id=workspace.owner_id,
        role="owner",
        member_count=0,
        created_at=workspace.created_at.isoformat(),
    )


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=201)
async def invite_member(
    workspace_id: str,
    data: InviteMemberRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    workspace = await repo.get_workspace(workspace_id)
    if not workspace:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
    member = await repo.add_member(
        workspace_id=workspace_id,
        email=data.email,
        role=data.role,
        invited_by=current_user["user_id"],
    )
    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        email=member.email,
        name=None,
        avatar_url=None,
        role=member.role.value,
        status=member.status.value,
        created_at=member.created_at.isoformat(),
    )


@router.post("/{workspace_id}/members/create", response_model=WorkspaceMemberResponse, status_code=201)
async def create_and_add_member(
    workspace_id: str,
    data: CreateMemberRequest,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    """Create a new user account and add them to the workspace."""
    from auth.repository import UserRepository
    from auth.model import AuthProvider
    from core.security import hash_password
    import asyncio

    workspace = await repo.get_workspace(workspace_id)
    if not workspace:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)

    session = repo._session
    user_repo = UserRepository(session)

    existing_user = await user_repo.get_user_by_email(data.email)
    if existing_user:
        raise CustomException(
            message="A user with this email already exists. Use invite instead.",
            code="EMAIL_EXISTS",
            status_code=409,
        )

    hashed = await asyncio.to_thread(hash_password, data.password)

    from auth.model import User, UserAccount
    user = User(
        email=data.email,
        full_name=data.full_name,
        username=data.email.split("@")[0],
    )
    session.add(user)
    await session.flush()

    account = UserAccount(
        user_id=user.id,
        provider=AuthProvider.PASSWORD,
        provider_user_id=data.email,
        password_hash=hashed,
    )
    session.add(account)
    await session.flush()

    from workspace.model import WorkspaceRole
    try:
        role = WorkspaceRole(data.role)
    except ValueError:
        raise CustomException(message="Invalid role", code="INVALID_ROLE", status_code=400)

    member = await repo.add_member(
        workspace_id=workspace_id,
        email=data.email,
        role=role,
        invited_by=current_user["user_id"],
        user_id=user.id,
    )

    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        email=member.email,
        name=data.full_name,
        avatar_url=None,
        role=member.role.value,
        status=member.status.value,
        created_at=member.created_at.isoformat(),
    )


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_members(
    workspace_id: str,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    workspace = await repo.get_workspace(workspace_id)
    if not workspace:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
    members = await repo.list_members(workspace_id)
    return [
        WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            email=m.email,
            name=None,
            avatar_url=None,
            role=m.role.value,
            status=m.status.value,
            created_at=m.created_at.isoformat(),
        )
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
    workspace = await repo.get_workspace(workspace_id)
    if not workspace:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
    member = await repo.get_member(member_id)
    if not member or member.workspace_id != workspace_id:
        raise CustomException(message="Member not found", code="NOT_FOUND", status_code=404)
    from workspace.model import WorkspaceRole
    try:
        role = WorkspaceRole(data.role)
    except ValueError:
        raise CustomException(message="Invalid role", code="INVALID_ROLE", status_code=400)
    member = await repo.update_member_role(member, role)
    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        email=member.email,
        name=None,
        avatar_url=None,
        role=member.role.value,
        status=member.status.value,
        created_at=member.created_at.isoformat(),
    )


@router.delete("/{workspace_id}/members/{member_id}", response_model=MessageResponse)
async def remove_member(
    workspace_id: str,
    member_id: str,
    current_user: CurrentUserDep,
    repo: WorkspaceRepoDep,
):
    workspace = await repo.get_workspace(workspace_id)
    if not workspace:
        raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
    member = await repo.get_member(member_id)
    if not member or member.workspace_id != workspace_id:
        raise CustomException(message="Member not found", code="NOT_FOUND", status_code=404)
    await repo.remove_member(member)
    return MessageResponse(message="Member removed")
