"""Runtime helpers for storing tenant-aware request context.

This module exposes a small API around a :class:`contextvars.ContextVar`
that keeps track of the current tenant during a request lifecycle. The
``TenantContextMiddleware`` populates the context by calling
``set_tenant_context`` and obtains a token that must be passed back to
``reset_tenant_context`` once the response has been sent. Other layers (for
example repositories or background services) can call
``get_current_tenant_id`` to discover which tenant is being served without
needing access to the original HTTP request object.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TypedDict

__all__ = [
    "TenantRuntimeContext",
    "get_current_tenant_id",
    "reset_tenant_context",
    "set_tenant_context",
]


class TenantRuntimeContext(TypedDict):
    """Values stored in the tenant context during a request."""

    tenant_id: str
    user_id: str


_tenant_context: ContextVar[TenantRuntimeContext | None] = ContextVar(
    "tenant_runtime_context", default=None
)


def set_tenant_context(tenant_id: str, user_id: str) -> Token[TenantRuntimeContext | None]:
    """Persist the tenant metadata in the request-scoped context variable.

    Args:
        tenant_id: Identifier of the tenant extracted from the JWT payload.
        user_id: Identifier of the authenticated user.

    Returns:
        ``Token`` returned by :meth:`contextvars.ContextVar.set`. Callers must
        later pass this token to :func:`reset_tenant_context` to restore the
        previous value once the response has been sent (the middleware performs
        this automatically).
    """

    return _tenant_context.set({"tenant_id": tenant_id, "user_id": user_id})


def reset_tenant_context(token: Token[TenantRuntimeContext | None]) -> None:
    """Restore the tenant context to the state prior to ``set_tenant_context``.

    Args:
        token: Handle returned by :func:`set_tenant_context`.
    """

    _tenant_context.reset(token)


def get_current_tenant_id() -> str | None:
    """Return the tenant identifier for the current execution context.

    The function returns ``None`` when the middleware has not populated the
    context, allowing downstream consumers to handle unauthenticated flows in
    a controlled fashion.
    """

    context = _tenant_context.get()
    if context is None:
        return None
    return context["tenant_id"]

