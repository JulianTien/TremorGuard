from typing import Annotated
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException, status
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_clerk_session_token, decode_token, hash_device_key
from app.db.session import get_clinical_session, get_identity_session
from app.models.clinical import DeviceBinding
from app.models.identity import RefreshToken, User


ClinicalSessionDep = Annotated[Session, Depends(get_clinical_session)]
IdentitySessionDep = Annotated[Session, Depends(get_identity_session)]


def get_current_user(
    identity_session: IdentitySessionDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    clerk_user_email: Annotated[str | None, Header(alias="X-Clerk-User-Email")] = None,
    clerk_user_name: Annotated[str | None, Header(alias="X-Clerk-User-Name")] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user = identity_session.scalar(select(User).where(User.id == payload["sub"], User.is_active.is_(True)))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        clerk_payload = decode_clerk_session_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Clerk token: {exc}",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive library/config mapping
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk token") from exc

    clerk_user_id = clerk_payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk token subject")

    normalized_email = (clerk_user_email or clerk_payload.get("email") or "").strip().lower()
    if not normalized_email:
        normalized_email = f"{clerk_user_id}@clerk.local"
    display_name = (unquote(clerk_user_name) if clerk_user_name else normalized_email.split("@")[0]).strip()
    display_name = display_name or "患者账号"

    user = identity_session.scalar(
        select(User).where(User.clerk_user_id == clerk_user_id, User.is_active.is_(True))
    )
    if not user:
        user = identity_session.scalar(select(User).where(User.email == normalized_email, User.is_active.is_(True)))
        if user:
            user.clerk_user_id = clerk_user_id
        else:
            user = User(
                email=normalized_email,
                clerk_user_id=clerk_user_id,
                display_name=display_name,
                status="pending_onboarding",
                onboarding_state="profile_required",
            )
            identity_session.add(user)
            identity_session.flush()
    else:
        email_owner = identity_session.scalar(
            select(User).where(User.email == normalized_email, User.id != user.id)
        )
        if not email_owner:
            user.email = normalized_email

    user.display_name = display_name
    user.is_active = True
    identity_session.commit()
    identity_session.refresh(user)
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_refresh_token(
    identity_session: IdentitySessionDep,
    refresh_token: str,
) -> RefreshToken | None:
    return identity_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == refresh_token))


def get_current_device_binding(
    clinical_session: ClinicalSessionDep,
    device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
) -> DeviceBinding:
    if not device_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing device key")

    key_hash = hash_device_key(device_key)
    device = clinical_session.scalar(
        select(DeviceBinding).where(
            DeviceBinding.api_key_hash == key_hash,
            DeviceBinding.is_active.is_(True),
            DeviceBinding.binding_status == "bound",
        )
    )
    if not device:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device key")
    return device


CurrentDeviceDep = Annotated[DeviceBinding, Depends(get_current_device_binding)]
