import importlib
from uuid import uuid4

from fastapi.testclient import TestClient


def create_client(monkeypatch, tenant_auth):
    # Reload modules to pick up env vars and database configuration
    import app.security.auth as auth
    importlib.reload(auth)
    import app.routers.admin_ingest_api as admin_api
    importlib.reload(admin_api)
    import app.main as main
    importlib.reload(main)

    client = TestClient(main.app)
    return client, admin_api, tenant_auth


def test_role_enforcement(monkeypatch, tenant_auth):
    client, admin_api, auth_ctx = create_client(monkeypatch, tenant_auth)
    dummy_job_id = uuid4()
    monkeypatch.setattr(admin_api.service, "ingest_url", lambda url: dummy_job_id)
    monkeypatch.setattr(admin_api.service, "list_jobs", lambda: [])

    # viewer can list jobs
    res = client.get("/api/admin/ingest/jobs", headers=auth_ctx.header("viewer"))
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}

    # viewer cannot start job
    res = client.post(
        "/api/admin/ingest/url",
        json={"url": "http://example.com"},
        headers=auth_ctx.header("viewer"),
    )
    assert res.status_code == 403

    # operator can start job
    res = client.post(
        "/api/admin/ingest/url",
        json={"url": "http://example.com"},
        headers=auth_ctx.header("operator"),
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == str(dummy_job_id)

    # missing key is unauthorized
    res = client.get("/api/admin/ingest/jobs")
    assert res.status_code == 401
