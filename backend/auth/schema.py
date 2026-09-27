from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum

from auth.model import AuthProvider


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"


# ── Request Schemas ──

class RegisterRequest(BaseModel):
    email: str
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    # The user confirmed they are 18 or older and accept the Terms and Privacy Policy.
    accept_terms: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address")
        return value


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address")
        return value


class OAuthLoginRequest(BaseModel):
    code: str
    redirect_uri: str
    # Required only when this sign-in creates the account: the user confirmed
    # they are 18 or older and accept the Terms and Privacy Policy.
    accept_terms: bool = False


# ── Response Schemas ──

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_verified: bool
    providers: list[AuthProvider]

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str
