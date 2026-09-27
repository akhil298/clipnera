from fastapi import APIRouter, Path, Request

from auth.dependencies import AuthServiceDep, CurrentUserDep
from auth.service import LoginClient
from auth.schema import (
    RegisterRequest,
    LoginRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
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
    return await auth_service.oauth_login(provider.value, data.code, data.redirect_uri, _login_client(request))


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
