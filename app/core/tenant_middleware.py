"""Middleware responsible for wiring tenant context into each request."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable

from app.models.session import get_engine
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

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
        if not self._is_configured() or self._should_bypass(request):
            return await call_next(request)

        authorization = request.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing Authorization header."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        scheme, _, credentials = authorization.partition(" ")
        if not credentials or scheme.lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authorization header must use Bearer scheme."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = await get_tenant_context(request)
        except HTTPException as exc:
            headers = dict(exc.headers or {})
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                headers.setdefault("WWW-Authenticate", "Bearer")
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=headers or None,
            )

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
        dialect = getattr(engine, "dialect", None)
        dialect_name = getattr(dialect, "name", "postgresql")
        if dialect_name != "postgresql":
            connection.close()
            return None
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

    @staticmethod
    def _should_bypass(request: Request) -> bool:
        if request.method.upper() == "OPTIONS":
            return True

        path = request.url.path
        
        # Public endpoints that don't require authentication
        public_endpoints = {
            "/api/health",
            "/api/version",
            "/api/config",
        }
        if path in public_endpoints:
            return True
        
        if not path.startswith("/api/tenant/accounts"):
            return False

        suffix = path.removeprefix("/api/tenant/accounts").lstrip("/")
        action = suffix.split("/", 1)[0]
        return action in {"register", "login", "refresh", "accept-invite"}
