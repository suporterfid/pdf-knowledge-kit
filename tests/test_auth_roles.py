import importlib

from fastapi.testclient import TestClient

import app.main as main
import app.security.auth as security_auth


def _create_client() -> TestClient:
    importlib.reload(security_auth)
    importlib.reload(main)
    return TestClient(main.app)


def test_roles_endpoint_valid_token(tenant_auth):
    client = _create_client()
    res = client.get("/api/auth/roles", headers=tenant_auth.header("viewer"))
    assert res.status_code == 200
    assert res.json() == {"roles": ["viewer"]}


def test_roles_endpoint_missing_token(tenant_auth):
    client = _create_client()
    res = client.get("/api/auth/roles")
    assert res.status_code == 401


def test_roles_endpoint_invalid_token(tenant_auth):
    client = _create_client()
    res = client.get("/api/auth/roles", headers={"Authorization": "Bearer invalid"})
    assert res.status_code == 401
