"""Middleware responsible for wiring tenant context into each request."""

from __future__ import annotations

import logging
import os
from typing import Callable, Awaitable

from fastapi import HTTPException, Request, status
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.models.session import get_engine

from .auth import TenantTokenPayload, get_tenant_context
from .tenant_context import reset_tenant_context, set_tenant_context

__all__ = ["TenantContextMiddleware"]

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Populate request state and database session with tenant metadata."""

    def __init__(self, app: ASGIApp, *, engine: Engine | None = None) -> None:
        super().__init__(app)
        self._engine = engine

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:  # type: ignore[override]
        if not self._is_configured():
            return await call_next(request)

        payload = await get_tenant_context(request)
        request.state.tenant_id = payload["tenant_id"]
        request.state.user_id = payload["user_id"]

        context_token = set_tenant_context(payload["tenant_id"], payload["user_id"])
        connection: Connection | None = None

        try:
            connection = self._prepare_connection(payload)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive, engine optional
            reset_tenant_context(context_token)
            logger.exception("Failed to configure tenant context for request.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to configure tenant context.",
            ) from exc

        try:
            return await call_next(request)
        finally:
            if connection is not None:
                try:
                    connection.execute(text("RESET app.tenant_id"))
                except SQLAlchemyError:  # pragma: no cover - best effort cleanup
                    logger.exception("Failed to reset tenant id configuration.")
                finally:
                    connection.close()
            reset_tenant_context(context_token)

    def _prepare_connection(self, payload: TenantTokenPayload) -> Connection | None:
        engine = self._resolve_engine()
        if engine is None:
            return None

        connection = engine.connect()
        try:
            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": payload["tenant_id"]},
            )
        except SQLAlchemyError:
            connection.close()
            raise
        return connection

    def _resolve_engine(self) -> Engine | None:
        if self._engine is not None:
            return self._engine

        try:
            self._engine = get_engine()
        except RuntimeError:
            logger.debug("Database engine not configured; skipping tenant set_config.")
            return None
        return self._engine

    @staticmethod
    def _is_configured() -> bool:
        required = (
            os.getenv("TENANT_TOKEN_SECRET"),
            os.getenv("TENANT_TOKEN_AUDIENCE"),
            os.getenv("TENANT_TOKEN_ISSUER"),
        )
        return all(required)

