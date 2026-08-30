from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class CreateMemberRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = "member"  # owner | admin | member | viewer


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"  # owner | admin | member | viewer


class UpdateMemberRoleRequest(BaseModel):
    role: str


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
