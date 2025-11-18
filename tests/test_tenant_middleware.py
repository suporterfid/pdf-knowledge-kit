"""Integration tests for the tenant context middleware."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

try:  # pragma: no cover - optional dependency guard
    from app.core.tenant_context import get_current_tenant_id
    from app.core.tenant_middleware import TenantContextMiddleware
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    pytest.skip(f"Required dependency missing: {exc.name}", allow_module_level=True)

jwt = pytest.importorskip("jwt")


@pytest.fixture(autouse=True)
def tenant_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the middleware is enabled by configuring token settings."""

    monkeypatch.setenv("TENANT_TOKEN_SECRET", "secret-key")
    monkeypatch.setenv("TENANT_TOKEN_AUDIENCE", "chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ISSUER", "auth.chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ALGORITHM", "HS256")


@dataclass
class DummyConnection:
    """Collect SQL statements executed by the middleware."""

    statements: list[tuple[str, dict[str, Any] | None]]

    def execute(
        self, statement: Any, params: dict[str, Any] | None = None
    ) -> None:  # pragma: no cover - trivial
        self.statements.append((str(statement), params))

    def close(self) -> None:  # pragma: no cover - trivial
        self.statements.append(("CLOSE", None))


@dataclass
class DummyEngine:
    """Return a deterministic connection for testing."""

    connection: DummyConnection

    def connect(self) -> DummyConnection:  # pragma: no cover - trivial
        return self.connection


def _create_app(
    monkeypatch: pytest.MonkeyPatch, connection: DummyConnection
) -> FastAPI:
    """Build a FastAPI application instrumented with the tenant middleware."""

    engine = DummyEngine(connection=connection)
    monkeypatch.setattr("app.core.tenant_middleware.get_engine", lambda: engine)

    app = FastAPI()
    app.add_middleware(TenantContextMiddleware)

    @app.get("/context")
    async def read_context(request: Request) -> JSONResponse:
        """Return the tenant context captured by the middleware."""

        return JSONResponse(
            {
                "tenant_id": request.state.tenant_id,
                "user_id": request.state.user_id,
                "context_tenant": get_current_tenant_id(),
            }
        )

    @app.get("/api/health")
    async def health() -> JSONResponse:
        """Public health endpoint."""
        return JSONResponse({"status": "ok"})

    @app.get("/api/version")
    async def version() -> JSONResponse:
        """Public version endpoint."""
        return JSONResponse({"version": "1.0.0"})

    @app.get("/api/config")
    async def config() -> JSONResponse:
        """Public config endpoint."""
        return JSONResponse({"BRAND_NAME": "Test"})

    return app


@pytest.fixture
def client_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], tuple[TestClient, DummyConnection]]:
    """Provide a factory that yields an isolated client and dummy connection."""

    def _factory() -> tuple[TestClient, DummyConnection]:
        connection = DummyConnection(statements=[])
        app = _create_app(monkeypatch, connection)
        client = TestClient(app, raise_server_exceptions=False)
        return client, connection

    return _factory


@pytest.fixture
def tenant_token_factory() -> Callable[..., str]:
    """Return a callable that issues signed tenant tokens for testing."""

    def _issue_token(
        *,
        tenant_id: str = "tenant-1",
        user_id: str = "user-1",
        expires_in: int = 300,
    ) -> str:
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "aud": "chatvolt",
            "iss": "auth.chatvolt",
            "exp": int(time.time()) + expires_in,
            "type": "access",
            "scope": "tenant",
        }
        token = jwt.encode(payload, "secret-key", algorithm="HS256")
        return str(token)

    return _issue_token


def test_middleware_sets_state_and_context(
    client_factory: Callable[[], tuple[TestClient, DummyConnection]],
    tenant_token_factory: Callable[..., str],
) -> None:
    """Ensure the middleware populates the request state and database context."""

    client, connection = client_factory()
    token = tenant_token_factory()

    response = client.get("/context", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "context_tenant": "tenant-1",
    }

    assert connection.statements[0][0].startswith("SELECT set_config")
    assert connection.statements[0][1] == {"tenant_id": "tenant-1"}
    assert connection.statements[1][0] == "RESET app.tenant_id"
    assert connection.statements[2][0] == "CLOSE"

    assert get_current_tenant_id() is None

    client.close()


def test_missing_token_returns_unauthorized(
    client_factory: Callable[[], tuple[TestClient, DummyConnection]],
) -> None:
    """Requests without credentials must fail with HTTP 401."""

    client, connection = client_factory()

    response = client.get("/context")

    assert response.status_code == 401
    assert connection.statements == []
    assert get_current_tenant_id() is None

    client.close()


def test_invalid_token_returns_unauthorized(
    client_factory: Callable[[], tuple[TestClient, DummyConnection]],
    tenant_token_factory: Callable[..., str],
) -> None:
    """Invalid tokens should trigger the HTTPException raised by auth helpers."""

    client, connection = client_factory()
    invalid_token = tenant_token_factory(tenant_id="tenant-2")[:-1] + "x"

    response = client.get(
        "/context", headers={"Authorization": f"Bearer {invalid_token}"}
    )

    assert response.status_code == 401
    assert connection.statements == []
    assert get_current_tenant_id() is None

    client.close()


def test_public_endpoints_bypass_auth(
    client_factory: Callable[[], tuple[TestClient, DummyConnection]],
) -> None:
    """Public endpoints should be accessible without authentication."""

    client, connection = client_factory()

    # Test /api/health endpoint
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Test /api/version endpoint
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"version": "1.0.0"}

    # Test /api/config endpoint
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"BRAND_NAME": "Test"}

    # Verify no database connection was made for public endpoints
    assert connection.statements == []
    assert get_current_tenant_id() is None

    client.close()
