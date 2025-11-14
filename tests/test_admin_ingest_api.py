import importlib
import sys
import types
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.ingestion.models import Source, SourceType
from fastapi.testclient import TestClient


def create_client(monkeypatch, tenant_auth):
    # Reload modules to pick up env vars and database configuration
    if "email_validator" not in sys.modules:
        sys.modules["email_validator"] = types.SimpleNamespace(
            validate_email=lambda value, **kwargs: types.SimpleNamespace(email=value),
            caching_resolver=None,
            EmailNotValidError=ValueError,
        )

    import pydantic.networks as pydantic_networks

    monkeypatch.setattr(pydantic_networks, "import_email_validator", lambda: None)

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
    monkeypatch.setattr(
        admin_api.service,
        "ingest_url",
        lambda url, *, tenant_id: dummy_job_id,
    )
    monkeypatch.setattr(admin_api.service, "list_jobs", lambda *, tenant_id: [])

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


def test_cross_tenant_source_isolation(monkeypatch, tenant_auth):
    client, admin_api, auth_ctx = create_client(monkeypatch, tenant_auth)
    tenant_sources: defaultdict[UUID, dict[UUID, Source]] = defaultdict(dict)

    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(admin_api, "_get_conn", lambda: DummyConn())

    def fake_get_or_create(conn, **kwargs):
        tenant_id = kwargs["tenant_id"]
        source_id = uuid4()
        source = Source(
            id=source_id,
            tenant_id=tenant_id,
            type=kwargs["type"],
            label=kwargs.get("label"),
            location=kwargs.get("location"),
            path=kwargs.get("path"),
            url=kwargs.get("url"),
            active=kwargs.get("active", True),
            params=kwargs.get("params"),
            connector_type=kwargs.get("connector_type"),
            connector_definition_id=kwargs.get("connector_definition_id"),
            connector_metadata=kwargs.get("connector_metadata"),
            credentials=kwargs.get("credentials"),
            sync_state=kwargs.get("sync_state"),
            version=kwargs.get("version") or 1,
            created_at=datetime.now(timezone.utc),
        )
        tenant_sources[tenant_id][source_id] = source
        return source_id

    monkeypatch.setattr(admin_api.storage, "get_or_create_source", fake_get_or_create)

    def fake_list_sources(conn, tenant_id, **kwargs):
        return list(tenant_sources.get(tenant_id, {}).values())

    monkeypatch.setattr(admin_api.storage, "list_sources", fake_list_sources)

    def fake_get_source(conn, source_id, *, tenant_id, **kwargs):
        return tenant_sources.get(tenant_id, {}).get(source_id)

    monkeypatch.setattr(admin_api.storage, "get_source", fake_get_source)

    def fake_soft_delete(conn, source_id, *, tenant_id):
        tenant_sources.get(tenant_id, {}).pop(source_id, None)

    monkeypatch.setattr(admin_api.storage, "soft_delete_source", fake_soft_delete)
    monkeypatch.setattr(admin_api.storage, "update_source", lambda *a, **k: None)

    create_payload = {
        "tenant_id": str(auth_ctx.organization_id),
        "type": SourceType.URL.value,
        "url": "http://tenant-a.test",
    }

    res = client.post(
        "/api/admin/ingest/sources",
        json=create_payload,
        headers=auth_ctx.header("operator"),
    )
    assert res.status_code == 200
    source_id = UUID(res.json()["id"])

    other_tenant = auth_ctx.create_tenant("Other", "other")

    res = client.get(
        "/api/admin/ingest/sources",
        headers=auth_ctx.header("viewer", tenant_id=other_tenant),
    )
    assert res.status_code == 200
    assert res.json()["items"] == []

    res = client.delete(
        f"/api/admin/ingest/sources/{source_id}",
        headers=auth_ctx.header("operator", tenant_id=other_tenant),
    )
    assert res.status_code == 404

    res = client.delete(
        f"/api/admin/ingest/sources/{source_id}",
        headers=auth_ctx.header("operator"),
    )
    assert res.status_code == 200
    assert not tenant_sources[auth_ctx.organization_id]
