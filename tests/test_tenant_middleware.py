"""Integration tests for the tenant context middleware."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

pytest.importorskip("sqlalchemy")
from app.core.tenant_context import get_current_tenant_id
from app.core.tenant_middleware import TenantContextMiddleware


@pytest.fixture(autouse=True)
def tenant_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the middleware is enabled by configuring token settings."""

    monkeypatch.setenv("TENANT_TOKEN_SECRET", "secret-key")
    monkeypatch.setenv("TENANT_TOKEN_AUDIENCE", "chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ISSUER", "auth.chatvolt")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _issue_token(*, tenant_id: str = "tenant-1", user_id: str = "user-1") -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "aud": "chatvolt",
        "iss": "auth.chatvolt",
        "exp": int(time.time()) + 300,
    }
    header_segment = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    payload_segment = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_segment}.{payload_segment}".encode()
    signature = hmac.new(b"secret-key", signing_input, hashlib.sha256).digest()
    signature_segment = _b64encode(signature)
    return ".".join([header_segment, payload_segment, signature_segment])


@dataclass
class DummyConnection:
    statements: list[str]

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> None:  # pragma: no cover - trivial
        self.statements.append(str(statement))

    def close(self) -> None:  # pragma: no cover - trivial
        self.statements.append("CLOSE")


@dataclass
class DummyEngine:
    connection: DummyConnection

    def connect(self) -> DummyConnection:
        return self.connection


def _create_app(engine: DummyEngine) -> FastAPI:
    app = FastAPI()
    app.add_middleware(TenantContextMiddleware, engine=engine)  # type: ignore[arg-type]

    @app.get("/context")
    async def read_context(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "tenant_id": request.state.tenant_id,
                "user_id": request.state.user_id,
                "context_tenant": get_current_tenant_id(),
            }
        )

    return app


def test_middleware_sets_state_and_context() -> None:
    connection = DummyConnection(statements=[])
    engine = DummyEngine(connection=connection)
    app = _create_app(engine)

    token = _issue_token()
    client = TestClient(app)
    response = client.get("/context", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "context_tenant": "tenant-1",
    }
    assert "set_config" in connection.statements[0]
    assert connection.statements[-2] == "RESET app.tenant_id"
    assert connection.statements[-1] == "CLOSE"
    assert get_current_tenant_id() is None


def test_missing_token_returns_unauthorized() -> None:
    connection = DummyConnection(statements=[])
    engine = DummyEngine(connection=connection)
    app = _create_app(engine)

    client = TestClient(app)
    response = client.get("/context")

    assert response.status_code == 401
    assert connection.statements == []
