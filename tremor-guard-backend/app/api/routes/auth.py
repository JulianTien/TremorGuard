from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ClinicalSessionDep, CurrentUserDep, IdentitySessionDep
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    hash_password,
    verify_password,
)
from app.models.identity import AuthCredential, RefreshToken, User
from app.schemas.auth import (
    AuthSessionResponse,
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RegisterRequest,
)
from app.services.user_management import sync_user_state

router = APIRouter()
settings = get_settings()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def issue_auth_session(
    user: User,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
    *,
    update_last_login: bool = True,
) -> AuthSessionResponse:
    current_user = sync_user_state(user, clinical_session)
    now = datetime.now(UTC)
    if update_last_login:
        user.last_login_at = now

    access_token = create_access_token(user.id)
    refresh_token, refresh_expires_at = create_refresh_token(user.id)
    identity_session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=refresh_expires_at,
        )
    )
    identity_session.commit()
    identity_session.refresh(user)

    current_user = sync_user_state(user, clinical_session)
    access_expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    return AuthSessionResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        current_user=current_user,
    )


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> AuthSessionResponse:
    existing_user = identity_session.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        status="pending_onboarding",
        onboarding_state="profile_required",
    )
    identity_session.add(user)
    identity_session.flush()
    identity_session.add(
        AuthCredential(
            user_id=user.id,
            password_hash=hash_password(payload.password),
            password_updated_at=datetime.now(UTC),
        )
    )
    return issue_auth_session(user, identity_session, clinical_session)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: LoginRequest,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> AuthSessionResponse:
    user = identity_session.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    credential = identity_session.scalar(select(AuthCredential).where(AuthCredential.user_id == user.id))
    if not credential or not verify_password(payload.password, credential.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return issue_auth_session(user, identity_session, clinical_session)


@router.post("/refresh", response_model=AuthSessionResponse)
def refresh(
    payload: RefreshRequest,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> AuthSessionResponse:
    token_hash = hash_token(payload.refresh_token)
    refresh_token_row = identity_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
    )
    if not refresh_token_row or ensure_utc(refresh_token_row.expires_at) < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = identity_session.scalar(
        select(User).where(User.id == refresh_token_row.user_id, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    refresh_token_row.revoked_at = datetime.now(UTC)
    identity_session.flush()
    return issue_auth_session(user, identity_session, clinical_session, update_last_login=False)


@router.post("/logout", response_model=LogoutResponse)
def logout(payload: LogoutRequest, identity_session: IdentitySessionDep) -> LogoutResponse:
    token_hash = hash_token(payload.refresh_token)
    refresh_token_row = identity_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
    )
    if refresh_token_row:
        refresh_token_row.revoked_at = datetime.now(UTC)
        identity_session.commit()

    return LogoutResponse()


@router.get("/session/me", response_model=CurrentUserResponse)
def get_current_session_user(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> CurrentUserResponse:
    return CurrentUserResponse(user=sync_user_state(current_user, clinical_session))
