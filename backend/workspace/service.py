from __future__ import annotations

import asyncio

from core.exceptions import CustomException
from core.security import hash_password
from workspace.model import Workspace, WorkspaceMember, WorkspaceRole
from workspace.repository import WorkspaceRepository
from workspace.schema import (
    CreateMemberRequest,
    CreateWorkspaceRequest,
    InviteMemberRequest,
    UpdateMemberRoleRequest,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)


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


class WorkspaceService:
    """Workspaces and their members; only the owner manages membership."""

    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repo = repository

    async def create_workspace(self, user_id: str, data: CreateWorkspaceRequest) -> WorkspaceResponse:
        user = (await self._repo.get_users_by_ids([user_id]))[user_id]
        workspace = await self._repo.create_workspace(data.name, user_id, user.email)
        return _workspace_response(workspace, WorkspaceRole.OWNER.value, 1)

    async def list_workspaces(self, user_id: str) -> list[WorkspaceResponse]:
        """The caller's workspaces. Anyone without one gets a personal workspace,
        so there is always somewhere to add team members."""
        results = await self._repo.list_for_user(user_id)
        if not results:
            user = (await self._repo.get_users_by_ids([user_id]))[user_id]
            owner_name = user.full_name or user.email.split("@")[0]
            workspace = await self._repo.create_workspace(f"{owner_name}'s Workspace", user_id, user.email)
            return [_workspace_response(workspace, WorkspaceRole.OWNER.value, 1)]
        return [_workspace_response(ws, role.value, count) for ws, role, count in results]

    async def get_workspace(self, workspace_id: str, user_id: str) -> WorkspaceResponse:
        membership = await self._require_membership(workspace_id, user_id)
        workspace = await self._repo.get_workspace(workspace_id)
        member_count = len(await self._repo.list_members(workspace_id))
        return _workspace_response(workspace, membership.role.value, member_count)

    async def invite_member(
        self, workspace_id: str, user_id: str, data: InviteMemberRequest
    ) -> WorkspaceMemberResponse:
        await self._require_owner(workspace_id, user_id)
        member = await self._repo.add_member(
            workspace_id=workspace_id,
            email=data.email,
            role=WorkspaceRole(data.role),
            invited_by=user_id,
        )
        return _member_response(member)

    async def create_member(
        self, workspace_id: str, user_id: str, data: CreateMemberRequest
    ) -> WorkspaceMemberResponse:
        """Create a regular user account and add it to the workspace.

        The account always gets the default ``user`` platform role; this can
        never create a platform admin.
        """
        await self._require_owner(workspace_id, user_id)
        if await self._repo.get_user_by_email(data.email):
            raise CustomException(
                message="A user with this email already exists. Use invite instead.",
                code="EMAIL_EXISTS",
                status_code=409,
            )

        hashed = await asyncio.to_thread(hash_password, data.password)
        user = await self._repo.add_password_user(data.email, data.full_name, hashed)
        member = await self._repo.add_member(
            workspace_id=workspace_id,
            email=data.email,
            role=WorkspaceRole(data.role),
            invited_by=user_id,
            user_id=user.id,
        )
        return _member_response(member, data.full_name)

    async def list_members(self, workspace_id: str, user_id: str) -> list[WorkspaceMemberResponse]:
        await self._require_membership(workspace_id, user_id)
        members = await self._repo.list_members(workspace_id)
        users = await self._repo.get_users_by_ids([m.user_id for m in members if m.user_id])
        return [
            _member_response(m, users[m.user_id].full_name if m.user_id in users else None)
            for m in members
        ]

    async def update_member_role(
        self, workspace_id: str, member_id: str, user_id: str, data: UpdateMemberRoleRequest
    ) -> WorkspaceMemberResponse:
        await self._require_owner(workspace_id, user_id)
        member = await self._get_editable_member(workspace_id, member_id)
        member = await self._repo.update_member_role(member, WorkspaceRole(data.role))
        return _member_response(member)

    async def remove_member(self, workspace_id: str, member_id: str, user_id: str) -> None:
        await self._require_owner(workspace_id, user_id)
        member = await self._get_editable_member(workspace_id, member_id)
        await self._repo.remove_member(member)

    async def _require_membership(self, workspace_id: str, user_id: str) -> WorkspaceMember:
        """The caller's membership; 404 for non-members so workspace ids don't leak."""
        workspace = await self._repo.get_workspace(workspace_id)
        membership = await self._repo.get_membership(workspace_id, user_id) if workspace else None
        if not membership:
            raise CustomException(message="Workspace not found", code="NOT_FOUND", status_code=404)
        return membership

    async def _require_owner(self, workspace_id: str, user_id: str) -> None:
        """Only the owner may add, re-role or remove members."""
        membership = await self._require_membership(workspace_id, user_id)
        if membership.role != WorkspaceRole.OWNER:
            raise CustomException(
                message="Only the workspace owner can manage members", code="FORBIDDEN", status_code=403
            )

    async def _get_editable_member(self, workspace_id: str, member_id: str) -> WorkspaceMember:
        member = await self._repo.get_member(member_id)
        if not member or member.workspace_id != workspace_id:
            raise CustomException(message="Member not found", code="NOT_FOUND", status_code=404)
        if member.role == WorkspaceRole.OWNER:
            raise CustomException(message="The workspace owner cannot be changed", code="FORBIDDEN", status_code=403)
        return member
