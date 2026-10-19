from html import escape

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from auth.dependencies import AuthServiceDep, CurrentUserDep
from auth.service import LoginClient
from core.exceptions import CustomException
from core.responses import ApiResponse, ok
from auth.schema import (
    RegisterRequest,
    LoginRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
    DesktopExchangeRequest,
    DesktopStartRequest,
    DesktopStartResponse,
    OAuthLoginRequest,
    OAuthProvider,
    TokenResponse,
    MessageResponse,
    UserResponse,
)

auth = APIRouter(prefix="/auth", tags=["auth"])


def _login_client(request: Request) -> LoginClient:
    # Behind nginx, uvicorn's proxy headers make request.client the visitor's address.
    return LoginClient(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@auth.post("/register", response_model=UserResponse, status_code=201)
async def register(request: Request, data: RegisterRequest, auth_service: AuthServiceDep):
    return await auth_service.register(data)


@auth.post("/login", response_model=TokenResponse)
async def login(request: Request, data: LoginRequest, auth_service: AuthServiceDep):
    return await auth_service.login(data.email, data.password, _login_client(request))


@auth.post("/logout", response_model=MessageResponse)
async def logout(request: Request, current_user: CurrentUserDep, auth_service: AuthServiceDep):
    await auth_service.logout(current_user["user_id"])
    return MessageResponse(message="Logged out successfully")


@auth.post("/oauth/{provider}", response_model=TokenResponse)
async def oauth_login(
    request: Request,
    provider: OAuthProvider = Path(..., description="OAuth provider"),
    data: OAuthLoginRequest = ...,
    auth_service: AuthServiceDep = ...,
):
    return await auth_service.oauth_login(
        provider.value, data.code, data.redirect_uri, _login_client(request), accept_terms=data.accept_terms
    )


@auth.post("/desktop/start", response_model=ApiResponse[DesktopStartResponse])
async def desktop_start(data: DesktopStartRequest, auth_service: AuthServiceDep):
    """Clipnera Studio for Mac: the Google sign-in link to open in the system browser."""
    return ok(await auth_service.desktop_start(data))


@auth.get("/desktop/callback", include_in_schema=False)
async def desktop_callback(
    auth_service: AuthServiceDep, state: str = "", code: str | None = None, error: str | None = None
):
    """Google returns here; the browser is sent on to the Mac app's 127.0.0.1 port."""
    try:
        return RedirectResponse(await auth_service.desktop_callback(state, code, error), status_code=302)
    except CustomException as exc:
        page = f"<!doctype html><title>Clipnera Studio</title><p>{escape(exc.message)}</p>"
        return HTMLResponse(page, status_code=exc.status_code)


@auth.post("/desktop/exchange", response_model=ApiResponse[TokenResponse])
async def desktop_exchange(request: Request, data: DesktopExchangeRequest, auth_service: AuthServiceDep):
    """Trade the one-time code from the callback, plus the app's PKCE verifier, for a session."""
    return ok(await auth_service.desktop_exchange(data.code, data.code_verifier, _login_client(request)))


@auth.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: Request, data: ForgotPasswordRequest, auth_service: AuthServiceDep):
    await auth_service.forgot_password(data.email)
    return MessageResponse(message="If the email exists, a reset link has been sent.")


@auth.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: Request, data: ResetPasswordRequest, auth_service: AuthServiceDep
):
    await auth_service.reset_password(data.token, data.new_password)
    return MessageResponse(message="Password reset successful.")
