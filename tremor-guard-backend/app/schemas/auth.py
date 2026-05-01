from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class ClerkSessionRequest(BaseModel):
    email: str
    display_name: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class CurrentUserDTO(BaseModel):
    id: str
    email: str
    display_name: str
    status: str
    onboarding_state: str
    last_login_at: datetime | None = None
    has_profile: bool
    has_bound_device: bool
    bound_device_serial: str | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    current_user: CurrentUserDTO


class CurrentUserResponse(BaseModel):
    user: CurrentUserDTO


class LogoutResponse(BaseModel):
    success: bool = True
