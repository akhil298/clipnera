from typing import Annotated, Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_admin
from auth.model import User
from core.database import get_db
from core.exceptions import CustomException
from core.security import decode_access_token
from feature_flags.admin_service import AuditActor, FlagAdminService
from feature_flags.context import FlagContext, load_context
from feature_flags.engine import flags
from feature_flags.repository import FlagRepository
from feature_flags.service import FeatureFlagService

SessionDep = Annotated[AsyncSession, Depends(get_db)]
ANON_COOKIE = "cn_anon"


def bearer_user_id(request: Request) -> str | None:
    """The signed-in user's id, None when no token was sent; 401 for a bad token."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    payload = decode_access_token(header[7:])
    if not payload:
        raise CustomException(message="Invalid or expired token", code="INVALID_TOKEN", status_code=401)
    return payload["sub"]


async def get_flag_context(request: Request, session: SessionDep) -> FlagContext:
    """Who the request is for, with optional auth. Role and plan are loaded only when a rule needs them.

    A bad token reads as anonymous here; the route's own auth decides whether to refuse it.
    """
    try:
        user_id = bearer_user_id(request)
    except CustomException:
        user_id = None
    ctx = FlagContext(user_id=user_id, anon_id=request.cookies.get(ANON_COOKIE))
    return await load_context(session, ctx, await flags.snapshot_for(session), include_config=False)


FlagContextDep = Annotated[FlagContext, Depends(get_flag_context)]


async def get_feature_flag_service(session: SessionDep, ctx: FlagContextDep) -> FeatureFlagService:
    return FeatureFlagService(session, ctx)


FeatureFlagServiceDep = Annotated[FeatureFlagService, Depends(get_feature_flag_service)]


def require_flag(key: str) -> Callable[..., Awaitable[None]]:
    """403 FEATURE_DISABLED while ``key`` (or anything it depends on) is off for the caller."""

    async def dependency(service: FeatureFlagServiceDep) -> None:
        await service.require(key)

    return dependency


def require_admin_permission(permission: str, legacy: bool = False) -> Callable[..., Awaitable[User]]:
    """The admin, if they hold ``permission`` (06-flags §6.2); 403 FORBIDDEN otherwise.

    ``legacy`` is for the two pre-revamp admin routes: an admin with no grants at all keeps
    the access every admin had before permissions existed, so admins promoted after the
    migration are not locked out of the current admin page. Grants, once given, apply.
    """

    async def dependency(admin: Annotated[User, Depends(get_current_admin)], session: SessionDep) -> User:
        granted = await FlagRepository(session).permissions(admin.id)
        if permission not in granted and not (legacy and not granted):
            raise CustomException(message="You do not have permission to do this.", code="FORBIDDEN",
                                  status_code=403, extra={"permission": permission})
        return admin

    return dependency


def admin_service_for(permission: str, legacy: bool = False) -> Callable[..., Awaitable[FlagAdminService]]:
    """A FlagAdminService acting as the admin, once ``permission`` is checked."""

    async def dependency(
        request: Request,
        session: SessionDep,
        admin: Annotated[User, Depends(require_admin_permission(permission, legacy))],
    ) -> FlagAdminService:
        actor = AuditActor(
            id=admin.id,
            email=admin.email,
            request_id=request.headers.get("X-Request-ID", "")[:64] or None,
            ip=request.client.host if request.client else None,
        )
        return FlagAdminService(session, actor)

    return dependency
