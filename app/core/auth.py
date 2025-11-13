"""Utilities for tenant-aware authentication."""

from __future__ import annotations

import os
from typing import TypedDict, cast

import jwt
from fastapi import HTTPException, Request, status
from jwt import ExpiredSignatureError, InvalidTokenError

__all__ = [
    "TenantTokenPayload",
    "TenantTokenConfigurationError",
    "TenantTokenValidationError",
    "decode_tenant_token",
    "get_tenant_context",
]


class TenantTokenConfigurationError(RuntimeError):
    """Raised when tenant token configuration is invalid."""


class TenantTokenValidationError(ValueError):
    """Raised when the provided tenant token cannot be validated."""


class _TenantTokenRequiredClaims(TypedDict):
    tenant_id: str
    user_id: str


class TenantTokenPayload(_TenantTokenRequiredClaims, total=False):
    """Decoded JWT payload for tenant-scoped authentication."""

    aud: str | list[str]
    email: str
    exp: int
    iat: int
    iss: str
    name: str
    roles: list[str]
    scope: str
    type: str


def _get_env(name: str, *, required: bool = True, default: str | None = None) -> str:
    """Fetch an environment variable with optional requirement enforcement.

    Args:
        name: Name of the environment variable to read.
        required: Whether to raise when the variable is missing or empty.
        default: Value to use when ``required`` is ``False`` and the variable is
            undefined.

    Returns:
        str: Stripped environment variable value or provided default.

    Raises:
        TenantTokenConfigurationError: If ``required`` is ``True`` and the
            variable is missing or blank.
    """

    value = os.getenv(name, default)
    if required and (value is None or not value.strip()):
        raise TenantTokenConfigurationError(
            f"Environment variable '{name}' must be set for tenant token validation.",
        )
    if value is None:
        return ""
    return value.strip()


def decode_tenant_token(token: str) -> TenantTokenPayload:
    """Decode and validate a tenant access token.

    Args:
        token: Encoded JWT token string from the ``Authorization`` header.

    Returns:
        TenantTokenPayload: Parsed payload containing tenant and user identifiers.

    Raises:
        TenantTokenConfigurationError: If mandatory environment configuration is missing.
        TenantTokenValidationError: If token signature, claims, or expiry are invalid.
    """

    secret_key = _get_env("TENANT_TOKEN_SECRET")
    audience = _get_env("TENANT_TOKEN_AUDIENCE")
    issuer = _get_env("TENANT_TOKEN_ISSUER")
    algorithm = _get_env("TENANT_TOKEN_ALGORITHM", required=False, default="HS256")

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "aud", "iss"]},
        )
    except ExpiredSignatureError as exc:
        raise TenantTokenValidationError("Tenant token has expired.") from exc
    except InvalidTokenError as exc:
        raise TenantTokenValidationError("Tenant token is invalid.") from exc

    if "tenant_id" not in payload or "user_id" not in payload:
        raise TenantTokenValidationError(
            "Tenant token payload must include 'tenant_id' and 'user_id'.",
        )
    type_claim = payload.get("type")
    if type_claim and type_claim != "access":
        raise TenantTokenValidationError("Tenant token must be an access token.")

    return cast(TenantTokenPayload, payload)


async def get_tenant_context(request: Request) -> TenantTokenPayload:
    """Extract tenant context from the ``Authorization`` header.

    Args:
        request: Incoming request whose headers may contain a bearer token.

    Returns:
        TenantTokenPayload: Validated tenant token payload for downstream dependencies.

    Raises:
        HTTPException: With status ``401`` when the header is missing or invalid,
            or ``500`` if the tenant token configuration is incorrect.
    """

    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    scheme, _, credentials = authorization.partition(" ")
    if not credentials or scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme.",
        )

    try:
        return decode_tenant_token(credentials)
    except TenantTokenConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except TenantTokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
