from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import AuthProvider, User, UserAccount
from auth.repository import UserRepository
from auth.oauth_service import OAuthService
from auth.provider import OAuthProvider
from auth.schema import RegisterRequest, TokenResponse, UserResponse
from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from core.security import create_access_token, verify_password
from subscription.model import PlanSlug
from subscription.repository import PlanRepository, UserSubscriptionRepository, PaymentTransactionRepository, CreditLedgerRepository
from subscription.service import SubscriptionService

settings = get_settings()
log = get_logger(__name__)


class AuthService:
    """Business logic for auth — all async, CPU-bound ops in thread pool."""

    def __init__(
        self,
        repository: UserRepository,
        oauth_service: OAuthService,
    ) -> None:
        self._repo = repository
        self._oauth = oauth_service

    async def _activate_free_plan(self, user_id: str) -> None:
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            plan_repo = PlanRepository(session)
            sub_repo = UserSubscriptionRepository(session)
            tx_repo = PaymentTransactionRepository(session)
            ledger_repo = CreditLedgerRepository(session)
            service = SubscriptionService(plan_repo, sub_repo, tx_repo, ledger_repo)
            try:
                await service.activate_free_plan(user_id)
            except Exception as exc:
                log.error(f"Failed to activate free plan for user {user_id}: {exc}")

    async def register(self, data: RegisterRequest) -> UserResponse:
        existing = await self._repo.get_user_by_email(data.email)
        if existing:
            log.warning(f"Registration failed: email already exists email={data.email}")
            raise CustomException(
                message="Email already registered",
                code="EMAIL_EXISTS",
                status_code=409,
            )

        user = await self._repo.create_user_with_password(data)
        log.info(f"User registered: user_id={user.id} email={user.email}")
        asyncio.create_task(self._activate_free_plan(user.id))
        return self._to_user_response(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._repo.get_user_by_email(email)
        if not user or not user.is_active:
            log.warning(f"Login failed: invalid credentials email={email}")
            raise CustomException(
                message="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        password_account = self._get_password_account(user)
        if not password_account:
            log.warning(f"Login failed: SSO-only account email={email}")
            raise CustomException(
                message="This account uses SSO login",
                code="SSO_ONLY",
                status_code=400,
            )

        is_valid = await asyncio.to_thread(verify_password, password, password_account.password_hash)
        if not is_valid:
            log.warning(f"Login failed: wrong password email={email}")
            raise CustomException(
                message="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        log.info(f"User logged in: user_id={user.id} email={email}")
        return self._create_token(user.id)

    async def oauth_login(self, provider: str, code: str, redirect_uri: str) -> TokenResponse:
        provider_enum = OAuthProvider.get_provider_enum(provider)

        if provider == "google":
            oauth_user = await self._oauth.verify_google(code, redirect_uri)
        elif provider == "microsoft":
            oauth_user = await self._oauth.verify_microsoft(code, redirect_uri)
        else:
            log.warning(f"OAuth login failed: unsupported provider={provider}")
            raise CustomException(
                message=f"Unsupported provider: {provider}",
                code="INVALID_PROVIDER",
                status_code=400,
            )

        provider_user_id = OAuthProvider.get_provider_user_id(provider, oauth_user)
        email = oauth_user.get("email") or oauth_user.get("mail") or oauth_user.get("userPrincipalName")
        log.info(f"OAuth login: provider={provider} email={email}")

        # Case 1: OAuth account exists → login
        account = await self._repo.get_account(provider_enum, provider_user_id)
        if account:
            log.info(f"OAuth login: existing account user_id={account.user_id}")
            return self._create_token(account.user_id)

        # Case 2: User with same email exists → link OAuth
        user = await self._repo.get_user_by_email(email)
        if user:
            await self._repo.link_oauth_account(
                user_id=user.id,
                provider=provider_enum,
                provider_user_id=provider_user_id,
            )
            log.info(f"OAuth login: linked to existing user user_id={user.id}")
            return self._create_token(user.id)

        # Case 3: New user → create
        user = await self._repo.create_oauth_user(
            email=email,
            full_name=oauth_user.get("name"),
            avatar_url=oauth_user.get("picture"),
        )
        await self._repo.link_oauth_account(
            user_id=user.id,
            provider=provider_enum,
            provider_user_id=provider_user_id,
        )
        log.info(f"OAuth login: new user created user_id={user.id}")
        asyncio.create_task(self._activate_free_plan(user.id))
        return self._create_token(user.id)

    async def forgot_password(self, email: str) -> None:
        user = await self._repo.get_user_by_email(email)
        if user:
            from auth.background_task import send_password_reset_email
            await send_password_reset_email(user.id, user.email)
            log.info(f"Password reset email sent: email={email}")

    async def logout(self, user_id: str) -> None:
        log.info(f"User logged out: user_id={user_id}")

    async def reset_password(self, token: str, new_password: str) -> None:
        from core.security import decode_access_token

        payload = decode_access_token(token)
        if not payload:
            raise CustomException(
                message="Invalid or expired token",
                code="INVALID_TOKEN",
                status_code=400,
            )

        user_id = payload.get("sub")
        user = await self._repo.get_user_by_id(user_id)
        if not user:
            raise CustomException(
                message="User not found",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        password_account = self._get_password_account(user)
        if not password_account:
            password_account = await self._repo.create_password_account(user.id, user.email)

        await self._repo.update_password(password_account, new_password)
        log.info(f"Password reset successful: user_id={user.id}")

    def _get_password_account(self, user: User) -> UserAccount | None:
        for account in user.accounts:
            if account.provider == AuthProvider.PASSWORD:
                return account
        return None

    def _create_token(self, user_id: str) -> TokenResponse:
        token = create_access_token(user_id)
        return TokenResponse(
            access_token=token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def _to_user_response(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_verified=user.is_verified,
            providers=[a.provider for a in user.accounts],
        )
