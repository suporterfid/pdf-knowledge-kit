import importlib
from uuid import uuid4

from fastapi.testclient import TestClient


def create_client(monkeypatch):
    monkeypatch.setenv("VIEW_API_KEY", "view")
    monkeypatch.setenv("OP_API_KEY", "oper")
    monkeypatch.setenv("ADMIN_API_KEY", "admin")

    # Reload modules to pick up env vars
    import app.security.auth as auth
    importlib.reload(auth)
    import app.routers.admin_ingest_api as admin_api
    importlib.reload(admin_api)
    import app.main as main
    importlib.reload(main)

    client = TestClient(main.app)
    return client, admin_api


def test_role_enforcement(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    dummy_job_id = uuid4()
    monkeypatch.setattr(admin_api.service, "ingest_url", lambda url: dummy_job_id)
    monkeypatch.setattr(admin_api.service, "list_jobs", lambda: [])

    # viewer can list jobs
    res = client.get("/api/admin/ingest/jobs", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}

    # viewer cannot start job
    res = client.post(
        "/api/admin/ingest/url",
        json={"url": "http://example.com"},
        headers={"X-API-Key": "view"},
    )
    assert res.status_code == 403

    # operator can start job
    res = client.post(
        "/api/admin/ingest/url",
        json={"url": "http://example.com"},
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == str(dummy_job_id)

    # missing key is unauthorized
    res = client.get("/api/admin/ingest/jobs")
    assert res.status_code == 401
