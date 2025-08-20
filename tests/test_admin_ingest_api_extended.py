import importlib
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    JobLogSlice,
    Source,
    SourceType,
)


def create_client(monkeypatch):
    monkeypatch.setenv("VIEWER_API_KEYS", "view")
    monkeypatch.setenv("OPERATOR_API_KEYS", "oper")
    monkeypatch.setenv("ADMIN_API_KEYS", "admin")
    import app.security.auth as auth
    importlib.reload(auth)
    import app.routers.admin_ingest_api as admin_api
    importlib.reload(admin_api)
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app), admin_api


def test_start_local_job_auth_validation(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    dummy_id = uuid4()
    monkeypatch.setattr(admin_api.service, "ingest_local", lambda *a, **k: dummy_id)

    # missing key
    res = client.post("/api/admin/ingest/jobs/local", params={"path": "/tmp/a"})
    assert res.status_code == 401

    # viewer forbidden
    res = client.post(
        "/api/admin/ingest/jobs/local",
        params={"path": "/tmp/a"},
        headers={"X-API-Key": "view"},
    )
    assert res.status_code == 403

    # validation error missing path
    res = client.post("/api/admin/ingest/jobs/local", headers={"X-API-Key": "oper"})
    assert res.status_code == 422

    # operator success
    res = client.post(
        "/api/admin/ingest/jobs/local",
        params={"path": "/tmp/a"},
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == str(dummy_id)


def test_start_urls_job_validation(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    dummy_id = uuid4()
    monkeypatch.setattr(admin_api.service, "ingest_urls", lambda urls: dummy_id)

    # validation error for body
    res = client.post("/api/admin/ingest/jobs/urls", headers={"X-API-Key": "oper"})
    assert res.status_code == 422

    res = client.post(
        "/api/admin/ingest/jobs/urls",
        json=["http://a"],
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == str(dummy_id)


def test_sources_crud_and_reindex(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    sources: dict[UUID, Source] = {}

    class DummyConn:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(admin_api, "_get_conn", lambda: DummyConn())

    def get_or_create(conn, type, path=None, url=None):
        sid = uuid4()
        sources[sid] = Source(id=sid, type=type, path=path, url=url, created_at=datetime.utcnow())
        return sid
    monkeypatch.setattr(admin_api.storage, "get_or_create_source", get_or_create)
    monkeypatch.setattr(admin_api.storage, "list_sources", lambda conn: sources.values())
    def update(conn, sid, path=None, url=None):
        src = sources[sid]
        if path:
            src.path = path
        if url:
            src.url = url
    monkeypatch.setattr(admin_api.storage, "update_source", update)
    monkeypatch.setattr(admin_api.storage, "soft_delete_source", lambda conn, sid: sources.pop(sid, None))
    called = {}
    monkeypatch.setattr(admin_api.service, "reindex_source", lambda sid: called.setdefault("rid", sid))

    # create
    res = client.post(
        "/api/admin/ingest/sources",
        params={"type": "local", "path": "/a"},
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    sid = UUID(res.json()["source_id"])

    # list
    res = client.get("/api/admin/ingest/sources", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert len(res.json()) == 1

    # update
    res = client.put(
        f"/api/admin/ingest/sources/{sid}",
        params={"path": "/b"},
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200

    # reindex
    res = client.post(
        f"/api/admin/ingest/sources/{sid}/reindex",
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert called["rid"] == sid

    # delete
    res = client.delete(
        f"/api/admin/ingest/sources/{sid}",
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200

    res = client.get("/api/admin/ingest/sources", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert res.json() == []


def test_job_lifecycle_and_logs(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    jobs: dict[UUID, IngestionJob] = {}
    slices = [
        JobLogSlice(text="line1\n", next_offset=6, total=12, status=None),
        JobLogSlice(text="line2\n", next_offset=12, total=12, status=IngestionJobStatus.COMPLETED),
    ]
    call = {"i": 0}

    def ingest_url(url):
        job_id = uuid4()
        jobs[job_id] = IngestionJob(
            id=job_id,
            source_id=uuid4(),
            status=IngestionJobStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        return job_id

    def list_jobs():
        return list(jobs.values())

    def cancel_job(job_id):
        jobs[job_id].status = IngestionJobStatus.CANCELED

    def read_job_log(job_id, offset=0, limit=16_384):
        i = call["i"]
        call["i"] = min(i + 1, len(slices) - 1)
        return slices[i]

    monkeypatch.setattr(admin_api.service, "ingest_url", ingest_url)
    monkeypatch.setattr(admin_api.service, "list_jobs", list_jobs)
    monkeypatch.setattr(admin_api.service, "cancel_job", cancel_job)
    monkeypatch.setattr(admin_api.service, "read_job_log", read_job_log)

    res = client.post(
        "/api/admin/ingest/jobs/url",
        params={"url": "http://example.com"},
        headers={"X-API-Key": "oper"},
    )
    job_id = UUID(res.json()["job_id"])

    res = client.get("/api/admin/ingest/jobs", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = client.post(
        f"/api/admin/ingest/jobs/{job_id}/cancel",
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert jobs[job_id].status == IngestionJobStatus.CANCELED

    res = client.get(
        f"/api/admin/ingest/jobs/{job_id}/logs", headers={"X-API-Key": "view"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "line1" in data["text"]
    assert data["next_offset"] == 6

    res = client.get(
        f"/api/admin/ingest/jobs/{job_id}/logs",
        params={"offset": data["next_offset"]},
        headers={"X-API-Key": "view"},
    )
    data = res.json()
    assert "line2" in data["text"]
    assert data["status"] == IngestionJobStatus.COMPLETED
