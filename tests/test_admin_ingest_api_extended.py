import importlib
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.ingestion.models import (
    Job,
    JobLogSlice,
    JobStatus,
    Source,
    SourceType,
)


def create_client(monkeypatch):
    monkeypatch.setenv("VIEW_API_KEY", "view")
    monkeypatch.setenv("OP_API_KEY", "oper")
    monkeypatch.setenv("ADMIN_API_KEY", "admin")
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
    res = client.post(
        "/api/admin/ingest/local", json={"path": "/tmp/a"}
    )
    assert res.status_code == 401

    # viewer forbidden
    res = client.post(
        "/api/admin/ingest/local",
        json={"path": "/tmp/a"},
        headers={"X-API-Key": "view"},
    )
    assert res.status_code == 403

    # validation error missing path
    res = client.post("/api/admin/ingest/local", headers={"X-API-Key": "oper"})
    assert res.status_code == 422

    # operator success
    res = client.post(
        "/api/admin/ingest/local",
        json={"path": "/tmp/a"},
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == str(dummy_id)


def test_start_urls_job_validation(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    dummy_id = uuid4()
    monkeypatch.setattr(admin_api.service, "ingest_urls", lambda urls: dummy_id)

    # validation error for body
    res = client.post("/api/admin/ingest/urls", headers={"X-API-Key": "oper"})
    assert res.status_code == 422

    res = client.post(
        "/api/admin/ingest/urls",
        json={"urls": ["http://a"]},
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

    def get_or_create(conn, **kwargs):
        sid = uuid4()
        sources[sid] = Source(
            id=sid,
            type=kwargs.get("type"),
            path=kwargs.get("path"),
            url=kwargs.get("url"),
            created_at=datetime.utcnow(),
        )
        return sid

    monkeypatch.setattr(admin_api.storage, "get_or_create_source", get_or_create)

    def list_sources(conn, **kwargs):
        return sources.values()

    monkeypatch.setattr(admin_api.storage, "list_sources", list_sources)

    def update(conn, sid, **kwargs):
        src = sources[sid]
        for k, v in kwargs.items():
            if v is not None:
                setattr(src, k, v)

    monkeypatch.setattr(admin_api.storage, "update_source", update)
    monkeypatch.setattr(
        admin_api.storage, "soft_delete_source", lambda conn, sid: sources.pop(sid, None)
    )
    called = {}
    monkeypatch.setattr(
        admin_api.service,
        "reindex_source",
        lambda sid: called.setdefault("rid", sid),
    )

    # create
    res = client.post(
        "/api/admin/ingest/sources",
        json={"type": "local_dir", "path": "/a"},
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    sid = UUID(res.json()["id"])

    # list
    res = client.get("/api/admin/ingest/sources", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    # update
    res = client.put(
        f"/api/admin/ingest/sources/{sid}",
        json={"path": "/b"},
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
    assert res.json()["items"] == []


def test_job_lifecycle_and_logs(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    jobs: dict[UUID, Job] = {}
    slices = [
        JobLogSlice(content="line1\n", next_offset=6, status=None),
        JobLogSlice(content="line2\n", next_offset=12, status=JobStatus.SUCCEEDED),
    ]
    call = {"i": 0}

    def ingest_url(url):
        job_id = uuid4()
        jobs[job_id] = Job(
            id=job_id,
            source_id=uuid4(),
            status=JobStatus.QUEUED,
            created_at=datetime.utcnow(),
        )
        return job_id

    def list_jobs():
        return list(jobs.values())

    def cancel_job(job_id):
        jobs[job_id].status = JobStatus.CANCELED

    def read_job_log(job_id, offset=0, limit=16_384):
        i = call["i"]
        call["i"] = min(i + 1, len(slices) - 1)
        return slices[i]

    monkeypatch.setattr(admin_api.service, "ingest_url", ingest_url)
    monkeypatch.setattr(admin_api.service, "list_jobs", list_jobs)
    monkeypatch.setattr(admin_api.service, "cancel_job", cancel_job)
    monkeypatch.setattr(admin_api.service, "read_job_log", read_job_log)
    monkeypatch.setattr(admin_api.service, "get_job", lambda jid: jobs.get(jid))

    res = client.post(
        "/api/admin/ingest/url",
        json={"url": "http://example.com"},
        headers={"X-API-Key": "oper"},
    )
    job_id = UUID(res.json()["job_id"])

    res = client.get("/api/admin/ingest/jobs", headers={"X-API-Key": "view"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = client.post(
        f"/api/admin/ingest/jobs/{job_id}/cancel",
        headers={"X-API-Key": "oper"},
    )
    assert res.status_code == 200
    assert jobs[job_id].status == JobStatus.CANCELED

    res = client.get(
        f"/api/admin/ingest/jobs/{job_id}/logs", headers={"X-API-Key": "view"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "line1" in data["content"]
    assert data["next_offset"] == 6

    res = client.get(
        f"/api/admin/ingest/jobs/{job_id}/logs",
        params={"offset": data["next_offset"]},
        headers={"X-API-Key": "view"},
    )
    data = res.json()
    assert "line2" in data["content"]
    assert data["status"] == JobStatus.SUCCEEDED


def test_rerun_job_endpoint(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    orig = uuid4()
    new_id = uuid4()
    monkeypatch.setattr(admin_api.service, "rerun_job", lambda jid: new_id)

    res = client.post(
        f"/api/admin/ingest/jobs/{orig}/rerun", headers={"X-API-Key": "oper"}
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == str(new_id)


def test_jobs_pagination_filters(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    jobs = [
        Job(id=uuid4(), source_id=uuid4(), status=JobStatus.QUEUED, created_at=datetime.utcnow()),
        Job(id=uuid4(), source_id=uuid4(), status=JobStatus.SUCCEEDED, created_at=datetime.utcnow()),
        Job(id=uuid4(), source_id=uuid4(), status=JobStatus.QUEUED, created_at=datetime.utcnow()),
    ]

    monkeypatch.setattr(admin_api.service, "list_jobs", lambda: jobs)

    res = client.get(
        "/api/admin/ingest/jobs",
        params={"status": "queued", "limit": 1, "offset": 1},
        headers={"X-API-Key": "view"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1


def test_sources_pagination_filters(monkeypatch):
    client, admin_api = create_client(monkeypatch)
    sources = [
        Source(id=uuid4(), type=SourceType.URL, url="http://a", path=None, created_at=datetime.utcnow(), active=True),
        Source(id=uuid4(), type=SourceType.URL, url="http://b", path=None, created_at=datetime.utcnow(), active=True),
        Source(id=uuid4(), type=SourceType.URL, url="http://c", path=None, created_at=datetime.utcnow(), active=False),
    ]

    class DummyConn:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    def list_sources(conn, active=True, type=None, **kwargs):
        items = sources
        if active is not None:
            items = [s for s in items if s.active == active]
        if type is not None:
            items = [s for s in items if s.type == type]
        return items

    monkeypatch.setattr(admin_api, "_get_conn", lambda: DummyConn())
    monkeypatch.setattr(admin_api.storage, "list_sources", list_sources)

    res = client.get(
        "/api/admin/ingest/sources",
        params={"type": "url", "limit": 1, "offset": 0},
        headers={"X-API-Key": "view"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
