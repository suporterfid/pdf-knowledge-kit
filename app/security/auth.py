"""Simple API-key based role authentication for FastAPI routers.

This module reads single API keys for roles from environment variables and
exposes a dependency factory ``require_role(min_role)`` that validates
``X-API-Key`` headers.

Role hierarchy (least → most privileged): ``viewer`` < ``operator`` < ``admin``.

Note: keys are loaded at import time; if you change the environment, restart
the server for changes to take effect.
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import Header, HTTPException, status

# Role hierarchy: higher number means more privileges
_ROLE_LEVELS = {"viewer": 0, "operator": 1, "admin": 2}


def _load_api_key_roles() -> dict[str, str]:
    """Load API keys for each role from environment variables.

    Environment variables expected:
    - ``VIEW_API_KEY`` (default: ``view``)
    - ``OP_API_KEY`` (default: ``oper``)
    - ``ADMIN_API_KEY`` (default: ``admin``)

    Each variable holds a single key for that role.
    """

    mapping: dict[str, str] = {}
    for env, role, default in [
        ("VIEW_API_KEY", "viewer", "view"),
        ("OP_API_KEY", "operator", "oper"),
        ("ADMIN_API_KEY", "admin", "admin"),
    ]:
        key = os.getenv(env, default).strip()
        if key:
            mapping[key] = role
    return mapping


_API_KEY_ROLES = _load_api_key_roles()


def require_role(min_role: str) -> Callable:
    """Create a dependency to validate the caller's role.

    The caller must supply an ``X-API-Key`` header whose value maps to a role
    with at least ``min_role`` privileges.

    Parameters
    ----------
    min_role:
        Minimum role name required (``viewer``, ``operator`` or ``admin``).

    Returns
    -------
    Callable
        FastAPI dependency that returns the resolved role string on success and
        raises ``HTTPException`` on failure.
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
