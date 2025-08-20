import pathlib
from threading import Event
from uuid import uuid4

import pytest

import app.ingestion.service as service
from app.ingestion.models import IngestionJobStatus


class ImmediateRunner:
    def submit(self, job_id, fn):
        ev = Event()
        fn(ev)
        class DummyFuture:
            def cancel(self):
                return False
        return DummyFuture()


def test_ingest_local_and_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "_runner", ImmediateRunner())
    path = tmp_path / "doc.md"
    path.write_text("hello", encoding="utf-8")
    job_id = service.ingest_local(path)
    job = service.get_job(job_id)
    assert job.status == IngestionJobStatus.COMPLETED
    log_path = pathlib.Path("logs") / "jobs" / f"{job_id}.log"
    assert log_path.exists()

    monkeypatch.setattr(service, "read_url_text", lambda url: "hi")
    job_id2 = service.ingest_url("http://example.com")
    job2 = service.get_job(job_id2)
    assert job2.status == IngestionJobStatus.COMPLETED


def test_ingest_local_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "_runner", ImmediateRunner())
    path = tmp_path / "bad.md"
    path.write_text("boom", encoding="utf-8")
    def bad(_):
        raise ValueError("fail")
    monkeypatch.setattr(service, "read_md_text", bad)
    job_id = service.ingest_local(path)
    job = service.get_job(job_id)
    assert job.status == IngestionJobStatus.FAILED
    assert job.error


def test_reindex_source_reingests(monkeypatch):
    source_id = uuid4()
    dummy_job = uuid4()
    called: dict[str, pathlib.Path] = {}

    class DummyCursor:
        def __init__(self):
            self.queries: list[tuple[str, tuple | None]] = []

        def execute(self, sql, params=None):
            self.queries.append((sql, params))

        def fetchone(self):
            # Return a LOCAL source pointing to a file
            return ("local", "/tmp/doc.md", None)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class DummyConn:
        def __init__(self):
            self.cur = DummyCursor()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self):
            return self.cur

        def commit(self):
            pass

    conn = DummyConn()
    monkeypatch.setattr(service.psycopg, "connect", lambda *a, **k: conn)
    monkeypatch.setattr(service, "register_vector", lambda conn: None)

    def fake_ingest(path):
        called["path"] = path
        return dummy_job

    monkeypatch.setattr(service, "ingest_local", fake_ingest)

    job_id = service.reindex_source(source_id)

    assert job_id == dummy_job
    assert called["path"] == pathlib.Path("/tmp/doc.md")
    assert any("DELETE FROM documents" in q[0] for q in conn.cur.queries)
