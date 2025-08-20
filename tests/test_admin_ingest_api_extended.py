import importlib
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.ingestion.models import IngestionJob, IngestionJobStatus, Source, SourceType


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
    log_states = ["", "line1\n", "line1\nline2\n"]
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

    def get_job(job_id):
        status = IngestionJobStatus.RUNNING if call["i"] < 2 else IngestionJobStatus.COMPLETED
        return IngestionJob(id=job_id, source_id=uuid4(), status=status, created_at=datetime.utcnow())

    def read_job_log(job_id):
        i = call["i"]
        call["i"] = min(i + 1, len(log_states) - 1)
        return log_states[i]

    async def fake_sleep(_):
        return None

    monkeypatch.setattr(admin_api.service, "ingest_url", ingest_url)
    monkeypatch.setattr(admin_api.service, "list_jobs", list_jobs)
    monkeypatch.setattr(admin_api.service, "cancel_job", cancel_job)
    monkeypatch.setattr(admin_api.service, "get_job", get_job)
    monkeypatch.setattr(admin_api.service, "read_job_log", read_job_log)
    monkeypatch.setattr(admin_api.asyncio, "sleep", fake_sleep)

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

    with client.stream(
        "GET", f"/api/admin/ingest/jobs/{job_id}/logs", headers={"X-API-Key": "view"}
    ) as res:
        raw = list(res.iter_lines())
    lines = [l.decode() if isinstance(l, bytes) else l for l in raw]
    assert any("line1" in l for l in lines)
    assert any("event: end" in l for l in lines)
