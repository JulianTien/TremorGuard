from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token, hash_device_key
from app.db.session import get_clinical_session, get_identity_session
from app.models.clinical import DeviceBinding
from app.models.identity import RefreshToken, User


ClinicalSessionDep = Annotated[Session, Depends(get_clinical_session)]
IdentitySessionDep = Annotated[Session, Depends(get_identity_session)]


def get_current_user(
    identity_session: IdentitySessionDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except Exception as exc:  # pragma: no cover - library error mapping
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = identity_session.scalar(select(User).where(User.id == payload["sub"], User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
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
