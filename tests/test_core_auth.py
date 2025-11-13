"""Tests for tenant-aware authentication helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from app.core.auth import (
    TenantTokenConfigurationError,
    TenantTokenPayload,
    TenantTokenValidationError,
    decode_tenant_token,
    get_tenant_context,
)
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for tenant token decoding."""

    monkeypatch.setenv("TENANT_TOKEN_SECRET", "secret-key")
    monkeypatch.setenv("TENANT_TOKEN_AUDIENCE", "chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ISSUER", "auth.chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ALGORITHM", "HS256")


def _issue_token(
    *,
    secret: str = "secret-key",
    audience: str = "chatvolt",
    issuer: str = "auth.chatvolt",
    tenant_id: str | None = "tenant-123",
    user_id: str | None = "user-456",
    **extra_claims: str | list[str] | int,
) -> str:
    """Generate a signed JWT for testing purposes."""

    payload: dict[str, object] = {
        "aud": audience,
        "iss": issuer,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    if user_id is not None:
        payload["user_id"] = user_id
    payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_tenant_token_success(token_env: None) -> None:
    """A valid token returns the decoded payload."""

    token = _issue_token(roles=["admin"])

    payload = decode_tenant_token(token)

    assert payload["tenant_id"] == "tenant-123"
    assert payload["user_id"] == "user-456"
    assert payload["roles"] == ["admin"]


def test_decode_tenant_token_missing_required_claims(token_env: None) -> None:
    """Tokens missing tenant or user identifiers are rejected."""

    token = _issue_token(user_id=None)

    with pytest.raises(TenantTokenValidationError):
        decode_tenant_token(token)


def test_decode_tenant_token_requires_access_type(token_env: None) -> None:
    """Tokens that are not access tokens are rejected."""

    token = _issue_token(type="refresh")

    with pytest.raises(TenantTokenValidationError):
        decode_tenant_token(token)


def test_decode_tenant_token_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing configuration raises a configuration error."""

    monkeypatch.delenv("TENANT_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("TENANT_TOKEN_AUDIENCE", raising=False)
    monkeypatch.delenv("TENANT_TOKEN_ISSUER", raising=False)

    with pytest.raises(TenantTokenConfigurationError):
        decode_tenant_token("token")


def _create_test_client() -> TestClient:
    """Create a FastAPI application wired with the tenant dependency."""

    app = FastAPI()

    @app.get("/tenant")
    async def read_tenant(
        payload: TenantTokenPayload = Depends(get_tenant_context),
    ) -> TenantTokenPayload:
        return payload

    return TestClient(app)


def test_get_tenant_context_success(token_env: None) -> None:
    """Dependency returns payload when a valid bearer token is supplied."""

    client = _create_test_client()
    token = _issue_token()

    response = client.get("/tenant", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-123"


def test_get_tenant_context_missing_header(token_env: None) -> None:
    """Missing Authorization header yields 401 Unauthorized."""

    client = _create_test_client()

    response = client.get("/tenant")

    assert response.status_code == 401


def test_get_tenant_context_invalid_scheme(token_env: None) -> None:
    """Non-bearer Authorization scheme is rejected."""

    client = _create_test_client()
    token = _issue_token()

    response = client.get("/tenant", headers={"Authorization": f"Token {token}"})

    assert response.status_code == 401


def test_get_tenant_context_invalid_signature(token_env: None) -> None:
    """An invalid token signature maps to 401 Unauthorized."""

    client = _create_test_client()
    token = _issue_token(secret="another-secret")

    response = client.get("/tenant", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_get_tenant_context_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuration issues propagate as HTTP 500 errors."""

    monkeypatch.delenv("TENANT_TOKEN_SECRET", raising=False)
    monkeypatch.setenv("TENANT_TOKEN_AUDIENCE", "chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ISSUER", "auth.chatvolt")

    client = _create_test_client()

    response = client.get("/tenant", headers={"Authorization": "Bearer token"})

    assert response.status_code == 500
