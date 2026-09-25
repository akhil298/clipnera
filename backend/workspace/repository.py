from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from auth.model import AuthProvider, User, UserAccount
from workspace.model import (
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    MemberStatus,
)


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class WorkspaceRepository:
    """Data access layer for workspaces and their members."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_workspace(self, name: str, owner_id: str, owner_email: str) -> Workspace:
        workspace = Workspace(name=name, slug=_slugify(name), owner_id=owner_id)
        self._session.add(workspace)
        await self._session.flush()

        owner_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            email=owner_email,
            role=WorkspaceRole.OWNER,
            status=MemberStatus.ACTIVE,
        )
        self._session.add(owner_member)
        await self._session.commit()
        await self._session.refresh(workspace)
        return workspace

    async def list_for_user(self, user_id: str) -> list[tuple[Workspace, str, int]]:
        others = aliased(WorkspaceMember)
        member_count = (
            select(func.count(others.id)).where(others.workspace_id == Workspace.id).scalar_subquery()
        )
        stmt = (
            select(Workspace, WorkspaceMember.role, member_count)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id, Workspace.is_active.is_(True))
        )
        result = await self._session.execute(stmt)
        return list(result.all())

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(
        self,
        workspace_id: str,
        email: str,
        role: WorkspaceRole,
        invited_by: str | None,
        user_id: str | None = None,
    ) -> WorkspaceMember:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            email=email,
            role=role,
            invited_by=invited_by,
            user_id=user_id,
            status=MemberStatus.ACTIVE if user_id else MemberStatus.PENDING,
        )
        self._session.add(member)
        await self._session.commit()
        await self._session.refresh(member)
        return member

    async def list_members(self, workspace_id: str) -> list[WorkspaceMember]:
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_membership(self, workspace_id: str, user_id: str) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_member(self, member_id: str) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(WorkspaceMember.id == member_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_member_role(self, member: WorkspaceMember, role: WorkspaceRole) -> WorkspaceMember:
        member.role = role
        await self._session.commit()
        await self._session.refresh(member)
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self._session.execute(delete(WorkspaceMember).where(WorkspaceMember.id == member.id))
        await self._session.commit()

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_password_user(self, email: str, full_name: str | None, password_hash: str) -> User:
        """Stage a password-login user; committed by the caller's next write."""
        user = User(email=email, full_name=full_name, username=email.split("@")[0])
        self._session.add(user)
        await self._session.flush()
        self._session.add(
            UserAccount(
                user_id=user.id,
                provider=AuthProvider.PASSWORD,
                provider_user_id=email,
                password_hash=password_hash,
            )
        )
        return user

    async def get_users_by_ids(self, user_ids: list[str]) -> dict[str, User]:
        if not user_ids:
            return {}
        stmt = select(User).where(User.id.in_(user_ids))
        result = await self._session.execute(stmt)
        return {u.id: u for u in result.scalars().all()}
