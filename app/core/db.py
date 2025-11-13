"""Database helpers for tenant-aware psycopg connections."""

from __future__ import annotations

import logging
from uuid import UUID

import psycopg

from .tenant_context import get_current_tenant_id

logger = logging.getLogger(__name__)


def apply_tenant_settings(
    conn: psycopg.Connection, tenant_id: str | UUID | None = None
) -> None:
    """Ensure ``app.tenant_id`` is configured for the provided connection."""

    effective = tenant_id or get_current_tenant_id()
    if effective is None:
        raise RuntimeError("tenant_id is required for tenant-scoped operations")

    tenant_value = str(effective)
    if not tenant_value:
        raise RuntimeError("tenant_id cannot be empty")

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, false)",
                (tenant_value,),
            )
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to apply tenant settings to connection")
        raise


def get_required_tenant_id(tenant_id: str | UUID | None = None) -> UUID:
    """Return the current tenant identifier or raise ``RuntimeError``."""

    effective = tenant_id or get_current_tenant_id()
    if effective is None:
        raise RuntimeError("Tenant context missing")
    if isinstance(effective, UUID):
        return effective
    try:
        return UUID(str(effective))
    except ValueError as exc:  # pragma: no cover - defensive
        raise RuntimeError("Invalid tenant identifier") from exc
