"""JWT-backed authentication dependencies for FastAPI routers."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import TenantTokenPayload, get_tenant_context
from app.models import User
from app.models.session import get_sessionmaker


_ROLE_LEVELS = {"viewer": 0, "operator": 1, "admin": 2}
_SESSION_FACTORY: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = get_sessionmaker()
    return _SESSION_FACTORY


def get_db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session for request-scoped dependencies."""

    session = _get_session_factory()()
    try:
        yield session
    finally:
        session.close()


async def get_current_token_payload(request: Request) -> TenantTokenPayload:
    """Decode and validate the bearer token from ``request``."""

    payload = await get_tenant_context(request)
    token_type = payload.get("type")
    if token_type and token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required.",
        )
    return payload


async def get_current_user(
    payload: TenantTokenPayload = Depends(get_current_token_payload),
    session: Session = Depends(get_db_session),
) -> User:
    """Resolve the authenticated :class:`~app.models.User` from the token payload."""

    try:
        user_id = uuid.UUID(payload["user_id"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier in token.",
        ) from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or no longer exists.",
        )

    if str(user.organization_id) != payload.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token tenant mismatch.",
        )

    return user


def _highest_role(roles: list[str]) -> str | None:
    ranked = sorted({role for role in roles if role in _ROLE_LEVELS}, key=_ROLE_LEVELS.get)
    return ranked[-1] if ranked else None


def require_role(min_role: str) -> Callable[..., str]:
    """Create a dependency ensuring the caller has at least ``min_role`` privileges."""

    if min_role not in _ROLE_LEVELS:
        raise ValueError(f"Unknown role: {min_role}")

    async def dependency(
        user: User = Depends(get_current_user),
        payload: TenantTokenPayload = Depends(get_current_token_payload),
    ) -> str:
        roles = payload.get("roles") or []
        if isinstance(roles, str):  # pragma: no cover - defensive
            roles = [roles]
        combined_roles = list(roles) + [user.role]
        highest = _highest_role(combined_roles)
        if highest is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No roles assigned to user.",
            )
        if _ROLE_LEVELS[highest] < _ROLE_LEVELS[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role.",
            )
        return highest

    return dependency


__all__ = [
    "get_current_token_payload",
    "get_current_user",
    "get_db_session",
    "require_role",
]
