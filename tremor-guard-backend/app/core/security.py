from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

import jwt
from jwt import PyJWKClient
from passlib.context import CryptContext

from app.core.config import get_settings

password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": "access",
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expires_at,
        "iat": now,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256"), expires_at


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def decode_clerk_session_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise ValueError("CLERK_JWKS_URL is not configured")

    signing_key = PyJWKClient(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
    decoded = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.clerk_audience or None,
        options={
            "verify_aud": bool(settings.clerk_audience),
            "verify_iss": False,
        },
    )

    if settings.clerk_issuer:
        accepted_issuers = {settings.clerk_issuer}
        if ".clerk.accounts.dev" in settings.clerk_issuer:
            accepted_issuers.add(settings.clerk_issuer.replace(".clerk.accounts.dev", ".accounts.dev"))
        if decoded.get("iss") not in accepted_issuers:
            raise jwt.InvalidIssuerError("Invalid issuer")

    return decoded


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def hash_device_key(raw_key: str) -> str:
    settings = get_settings()
    return sha256(f"{settings.device_key_salt}:{raw_key}".encode()).hexdigest()
