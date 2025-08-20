from __future__ import annotations

import os
from typing import Callable

from fastapi import Header, HTTPException, status

# Role hierarchy: higher number means more privileges
_ROLE_LEVELS = {"viewer": 0, "operator": 1, "admin": 2}


def _load_api_key_roles() -> dict[str, str]:
    """Load API keys for each role from environment variables.

    Environment variables expected:
    - ``VIEWER_API_KEYS``
    - ``OPERATOR_API_KEYS``
    - ``ADMIN_API_KEYS``

    Each variable may contain a comma-separated list of keys for that role.
    """

    mapping: dict[str, str] = {}
    for role in _ROLE_LEVELS:
        keys = os.getenv(f"{role.upper()}_API_KEYS", "")
        for key in [k.strip() for k in keys.split(",") if k.strip()]:
            mapping[key] = role
    return mapping


_API_KEY_ROLES = _load_api_key_roles()


def require_role(min_role: str) -> Callable:
    """Return a dependency that validates the caller's role.

    The caller must supply an ``X-API-Key`` header whose value maps to a role
    with at least ``min_role`` privileges. Roles are hierarchical in the order:
    ``viewer`` < ``operator`` < ``admin``.
    """

    if min_role not in _ROLE_LEVELS:
        raise ValueError(f"Unknown role: {min_role}")

    async def dependency(x_api_key: str | None = Header(default=None)) -> str:
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
            )
        role = _API_KEY_ROLES.get(x_api_key)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        if _ROLE_LEVELS[role] < _ROLE_LEVELS[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return role

    return dependency
