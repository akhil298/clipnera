from __future__ import annotations

import re
from auth.model import User, AuthProvider
from user.repository import UserRepository


class UserService:
    """Profile related business logic."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def get_profile(self, user_id: str) -> User | None:
        return await self._repository.get_by_id(user_id)

    @staticmethod
    def _get_initials(name: str | None, email: str) -> str:
        if name:
            parts = re.split(r"\s+", name.strip())
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            return name[:2].upper()
        return email[:2].upper() if email else "U"

    @staticmethod
    def to_response(user: User) -> "UserProfileResponse":  # type: ignore[name-defined]
        from user.schema import UserProfileResponse

        display_name = user.full_name or user.username or user.email.split("@")[0]
        return UserProfileResponse(
            id=user.id,
            name=display_name,
            email=user.email,
            avatar_url=user.avatar_url,
            avatar_initials=UserService._get_initials(display_name, user.email),
            active_workspace_id=None,
            providers=[a.provider.value for a in user.accounts],
        )
