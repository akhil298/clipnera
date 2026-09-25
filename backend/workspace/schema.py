from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# Roles an owner can give someone. Owner and admin are never assignable, so
# nobody can be promoted to manage a workspace through the API.
AssignableRole = Literal["member", "viewer"]


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class CreateMemberRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: AssignableRole = "member"


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: AssignableRole = "member"


class UpdateMemberRoleRequest(BaseModel):
    role: AssignableRole


class WorkspaceMemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: Optional[str] = None
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    status: str
    created_at: str


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str
    role: str
    member_count: int
    created_at: str
