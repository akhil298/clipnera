from __future__ import annotations

from typing import TYPE_CHECKING

from auth.model import AuthProvider

if TYPE_CHECKING:
    pass


class OAuthProvider:
    """Maps provider enum to OAuth service methods."""

    @staticmethod
    def get_provider_enum(provider_str: str) -> AuthProvider:
        mapping = {
            "google": AuthProvider.GOOGLE,
            "microsoft": AuthProvider.MICROSOFT,
        }
        try:
            return mapping[provider_str]
        except KeyError:
            from core.exceptions import CustomException
            raise CustomException(
                message=f"Unsupported provider: {provider_str}",
                code="INVALID_PROVIDER",
                status_code=400,
            )

    @staticmethod
    def get_provider_user_id(provider: str, oauth_user: dict) -> str:
        if provider == "google":
            return oauth_user["sub"]
        if provider == "microsoft":
            return oauth_user["id"]
        from core.exceptions import CustomException
        raise CustomException(
            message=f"Unsupported provider: {provider}",
            code="INVALID_PROVIDER",
            status_code=400,
        )
