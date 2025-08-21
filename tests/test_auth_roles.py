from fastapi.testclient import TestClient
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_roles_endpoint_valid_key():
    res = client.get("/api/auth/roles", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert res.json() == {"roles": ["viewer"]}


def test_roles_endpoint_missing_key():
    res = client.get("/api/auth/roles")
    assert res.status_code == 401


def test_roles_endpoint_invalid_key():
    res = client.get("/api/auth/roles", headers={"X-API-Key": "bad"})
    assert res.status_code == 401
