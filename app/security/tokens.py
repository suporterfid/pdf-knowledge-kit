"""Helpers for issuing and managing JWT access/refresh tokens."""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import os
import secrets
from collections.abc import Iterable
from functools import lru_cache
from typing import Any, cast

import jwt
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.models import RefreshToken, User


@dataclasses.dataclass(frozen=True)
class JWTSettings:
    """Runtime configuration for issuing authentication tokens."""

    secret: str
    issuer: str
    audience: str
    algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14  # two weeks


@lru_cache(maxsize=1)
def get_jwt_settings() -> JWTSettings:
    """Load settings from the environment with sane defaults for development."""

    secret = os.getenv("TENANT_TOKEN_SECRET")
    issuer = os.getenv("TENANT_TOKEN_ISSUER")
    audience = os.getenv("TENANT_TOKEN_AUDIENCE")
    algorithm = os.getenv("TENANT_TOKEN_ALGORITHM", "HS256")
    if not secret or not issuer or not audience:
        raise RuntimeError(
            "TENANT_TOKEN_SECRET, TENANT_TOKEN_ISSUER and TENANT_TOKEN_AUDIENCE must be set.",
        )
    access_ttl = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
    refresh_ttl = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 14)))
    return JWTSettings(
        secret=secret,
        issuer=issuer,
        audience=audience,
        algorithm=algorithm,
        access_token_ttl_seconds=access_ttl,
        refresh_token_ttl_seconds=refresh_ttl,
    )


def reset_jwt_settings_cache() -> None:
    """Clear cached JWT settings; useful in tests when env vars change."""

    get_jwt_settings.cache_clear()


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _user_roles(user: User) -> list[str]:
    roles: Iterable[str]
    if isinstance(user.role, str):
        roles = [user.role]
    else:  # pragma: no cover - defensive, role stored as str
        roles = list(user.role)
    return [role for role in roles if role]


def create_access_token(
    user: User, *, settings: JWTSettings | None = None
) -> tuple[str, dt.datetime]:
    """Issue a signed JWT access token for ``user``."""

    settings = settings or get_jwt_settings()
    now = _utcnow()
    expires_at = now + dt.timedelta(seconds=settings.access_token_ttl_seconds)
    payload: dict[str, Any] = {
        "tenant_id": str(user.organization_id),
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "roles": _user_roles(user),
        "iss": settings.issuer,
        "aud": settings.audience,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "scope": "tenant",
        "type": "access",
    }
    token = jwt.encode(payload, settings.secret, algorithm=settings.algorithm)
    return str(token), expires_at


def create_refresh_token(
    session: Session,
    user: User,
    *,
    user_agent: str | None = None,
    settings: JWTSettings | None = None,
) -> tuple[str, RefreshToken]:
    """Persist a refresh token bound to ``user`` and return the raw secret."""

    settings = settings or get_jwt_settings()
    raw_token = secrets.token_urlsafe(48)
    hashed = _hash_token(raw_token)
    now = _utcnow()
    expires_at = now + dt.timedelta(seconds=settings.refresh_token_ttl_seconds)
    record = RefreshToken(
        user_id=user.id,
        token_hash=hashed,
        issued_at=now,
        expires_at=expires_at,
        user_agent=user_agent,
    )
    session.add(record)
    session.flush()
    return raw_token, record


def verify_refresh_token(session: Session, raw_token: str) -> RefreshToken | None:
    """Return the refresh token row matching ``raw_token`` if valid."""

    if not raw_token:
        return None
    hashed = _hash_token(raw_token)
    token = session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hashed)
    ).scalar_one_or_none()
    if token is None:
        return None
    if token.revoked_at is not None:
        return None
    if _as_utc(token.expires_at) <= _utcnow():
        return None
    return token


def revoke_refresh_token(
    token: RefreshToken, *, when: dt.datetime | None = None
) -> None:
    """Mark ``token`` as revoked."""

    token.revoked_at = when or _utcnow()


def revoke_all_refresh_tokens(
    session: Session, user: User, *, when: dt.datetime | None = None
) -> int:
    """Revoke every refresh token for ``user`` and return the count."""

    when = when or _utcnow()
    result = session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
        .execution_options(synchronize_session="fetch")
    )
    cursor_result = cast(CursorResult[Any], result)
    return int(cursor_result.rowcount or 0)


__all__ = [
    "JWTSettings",
    "create_access_token",
    "create_refresh_token",
    "get_jwt_settings",
    "reset_jwt_settings_cache",
    "revoke_all_refresh_tokens",
    "revoke_refresh_token",
    "verify_refresh_token",
]
