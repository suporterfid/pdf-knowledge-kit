import os
import pathlib
import uuid
from datetime import datetime
from threading import Event
from uuid import uuid4

import psycopg
import pytest

import app.ingestion.service as service
from app.ingestion.models import JobStatus


class ImmediateRunner:
    def submit(self, job_id, fn):
        ev = Event()
        fn(ev)
        class DummyFuture:
            def cancel(self):
                return False
        return DummyFuture()

    def cancel(self, job_id):
        return None

    def clear(self, job_id):
        return None


class DummyCursor:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def execute(self, *a, **k):
        return None
    def fetchone(self):
        return None


class DummyConn:
    def cursor(self):
        return DummyCursor()
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def commit(self):
        return None


def test_ingest_local_and_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "_runner", ImmediateRunner())
    class DummyEmbedder:
        def embed(self, texts):
            for _ in texts:
                yield [0.0]
    monkeypatch.setattr(service, "TextEmbedding", lambda model_name: DummyEmbedder())
    monkeypatch.setattr(service.psycopg, "connect", lambda *a, **k: DummyConn())
    monkeypatch.setattr(service, "register_vector", lambda conn: None)
    src_id = uuid4()
    monkeypatch.setattr(service.storage, "get_or_create_source", lambda *a, **k: src_id)

    jobs: dict[uuid.UUID, service.Job] = {}

    def create_job(conn, source_id, status=JobStatus.QUEUED, params=None):
        jid = uuid4()
        jobs[jid] = service.Job(
            id=jid,
            source_id=source_id,
            status=status,
            created_at=datetime.utcnow(),
        )
        return jid

    def update_job_status(conn, job_id, status, **kwargs):
        job = jobs[job_id]
        job.status = status
        if "error" in kwargs:
            job.error = kwargs["error"]
        if "log_path" in kwargs:
            job.log_path = kwargs["log_path"]

    def get_job(conn, job_id):
        return jobs.get(job_id)

    monkeypatch.setattr(service.storage, "create_job", create_job)
    monkeypatch.setattr(service.storage, "update_job_status", update_job_status)
    monkeypatch.setattr(service.storage, "get_job", get_job)
    monkeypatch.setattr(service, "upsert_document", lambda *a, **k: uuid4())
    monkeypatch.setattr(service, "insert_chunks", lambda *a, **k: None)
    path = tmp_path / "doc.md"
    path.write_text("hello", encoding="utf-8")
    job_id = service.ingest_local(path)
    job = service.get_job(job_id)
    assert job and job.status == JobStatus.SUCCEEDED
    log_path = pathlib.Path("logs") / "jobs" / f"{job_id}.log"
    assert log_path.exists()

    dummy_job = uuid4()
    jobs[dummy_job] = service.Job(
        id=dummy_job,
        source_id=uuid4(),
        status=JobStatus.SUCCEEDED,
        created_at=datetime.utcnow(),
    )
    monkeypatch.setattr(service, "ingest_url", lambda url: dummy_job)
    job2 = service.get_job(service.ingest_url("http://example.com"))
    assert job2 and job2.status == JobStatus.SUCCEEDED


def test_ingest_local_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "_runner", ImmediateRunner())
    monkeypatch.setattr(service.psycopg, "connect", lambda *a, **k: DummyConn())
    monkeypatch.setattr(service, "register_vector", lambda conn: None)
    monkeypatch.setattr(service.storage, "get_or_create_source", lambda *a, **k: uuid4())

    jobs: dict[uuid.UUID, service.Job] = {}

    def create_job(conn, source_id, status=JobStatus.QUEUED, params=None):
        jid = uuid4()
        jobs[jid] = service.Job(
            id=jid,
            source_id=source_id,
            status=status,
            created_at=datetime.utcnow(),
        )
        return jid

    def update_job_status(conn, job_id, status, **kwargs):
        job = jobs[job_id]
        job.status = status
        if "error" in kwargs:
            job.error = kwargs["error"]

    def get_job(conn, job_id):
        return jobs.get(job_id)

    monkeypatch.setattr(service.storage, "create_job", create_job)
    monkeypatch.setattr(service.storage, "update_job_status", update_job_status)
    monkeypatch.setattr(service.storage, "get_job", get_job)
    path = tmp_path / "bad.md"
    path.write_text("boom", encoding="utf-8")
    def bad(_):
        raise ValueError("fail")
    monkeypatch.setattr(service, "read_md_text", bad)
    job_id = service.ingest_local(path)
    job = service.get_job(job_id)
    assert job and job.status == JobStatus.FAILED
    assert job.error


def test_ingest_local_ocr_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "_runner", ImmediateRunner())
    monkeypatch.setattr(service.psycopg, "connect", lambda *a, **k: DummyConn())
    monkeypatch.setattr(service, "register_vector", lambda conn: None)
    monkeypatch.setattr(service.storage, "get_or_create_source", lambda *a, **k: uuid4())

    jobs: dict[uuid.UUID, service.Job] = {}

    def create_job(conn, source_id, status=JobStatus.QUEUED, params=None):
        jid = uuid4()
        jobs[jid] = service.Job(
            id=jid,
            source_id=source_id,
            status=status,
            created_at=datetime.utcnow(),
        )
        return jid

    def update_job_status(conn, job_id, status, **kwargs):
        job = jobs[job_id]
        job.status = status
        if "error" in kwargs:
            job.error = kwargs["error"]
        if "log_path" in kwargs:
            job.log_path = kwargs["log_path"]

    def get_job(conn, job_id):
        return jobs.get(job_id)

    monkeypatch.setattr(service.storage, "create_job", create_job)
    monkeypatch.setattr(service.storage, "update_job_status", update_job_status)
    monkeypatch.setattr(service.storage, "get_job", get_job)
    pdf_path = tmp_path / "doc.pdf"
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as fh:
        writer.write(fh)

    def fail_ocr(path, use_ocr=False, ocr_lang=None):
        raise RuntimeError("ocr boom")

    monkeypatch.setattr(service, "read_pdf_text", fail_ocr)
    monkeypatch.setattr(service, "TextEmbedding", lambda model_name: type("E", (), {"embed": lambda self, texts: []})())

    job_id = service.ingest_local(pdf_path, use_ocr=True)
    job = service.get_job(job_id)
    assert job and job.status == JobStatus.FAILED
    assert job.error and "ocr boom" in job.error


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
            # Return a LOCAL_DIR source pointing to a file
            return ("local_dir", "/tmp/doc.md", None)

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


def test_rerun_job_calls_reindex(monkeypatch):
    job_id = uuid4()
    source_id = uuid4()
    new_job_id = uuid4()
    called: dict[str, uuid.UUID] = {}

    class DummyCursor:
        def __init__(self):
            self.queries: list[tuple[str, tuple | None]] = []

        def execute(self, sql, params=None):
            self.queries.append((sql, params))

        def fetchone(self):
            return (source_id,)

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
    monkeypatch.setattr(service, "ensure_schema", lambda *a, **k: None)
    def fake_reindex(sid):
        called["sid"] = sid
        return new_job_id

    monkeypatch.setattr(service, "reindex_source", fake_reindex)

    result = service.rerun_job(job_id)

    assert result == new_job_id
    assert called["sid"] == source_id
    assert any(
        "SELECT source_id FROM ingestion_jobs" in q[0] for q in conn.cur.queries
    )


@pytest.mark.integration
def test_ingest_local_integration_persists_chunks(tmp_path, monkeypatch):
    testing_postgresql = pytest.importorskip("testing.postgresql")
    try:
        pg = testing_postgresql.Postgresql()
    except RuntimeError as exc:
        pytest.skip(f"testing.postgresql is unavailable: {exc}")
    monkeypatch.setenv("DATABASE_URL", pg.url())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "_runner", ImmediateRunner())

    class DummyEmbedder:
        def embed(self, texts):
            for text in texts:
                yield [float(len(text)), float(len(text)) / 2.0]

    monkeypatch.setattr(service, "TextEmbedding", lambda model_name: DummyEmbedder())

    def ensure_schema_without_vector(conn, schema_sql_path=service.SCHEMA_PATH, migrations_dir=None):
        sql = pathlib.Path(schema_sql_path).read_text(encoding="utf-8")
        sql = sql.replace(
            "CREATE EXTENSION IF NOT EXISTS vector;",
            "-- vector extension skipped in tests",
        )
        sql = sql.replace("VECTOR(384)", "DOUBLE PRECISION[]")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    monkeypatch.setattr(service, "ensure_schema", ensure_schema_without_vector)
    monkeypatch.setattr(service, "register_vector", lambda conn: None)

    note_path = tmp_path / "integration.md"
    note_path.write_text("integration test content", encoding="utf-8")

    try:
        job_id = service.ingest_local(note_path)
        job = service.get_job(job_id)
        assert job and job.status == JobStatus.SUCCEEDED

        with psycopg.connect(pg.url()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT content, metadata, embedding FROM chunks")
                row = cur.fetchone()
                assert row is not None
                content, metadata, embedding = row
                assert content == "integration test content"
                assert metadata["mime_type"] == "text/markdown"
                assert metadata["source_path"] == str(note_path)
                assert metadata["page_number"] == 1
                assert isinstance(embedding, list)
                assert pytest.approx(embedding[0]) == float(len(content))
    finally:
        pg.stop()


def test_read_job_log_slicing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job_id = uuid4()
    log_dir = pathlib.Path("logs") / "jobs"
    log_dir.mkdir(parents=True)
    log_path = log_dir / f"{job_id}.log"
    log_path.write_text("line1\nline2\n", encoding="utf-8")
    jobs: dict[uuid.UUID, service.Job] = {
        job_id: service.Job(
            id=job_id,
            source_id=uuid4(),
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            log_path=str(log_path),
        )
    }

    monkeypatch.setattr(service.psycopg, "connect", lambda *a, **k: DummyConn())

    def get_job(conn, jid):
        return jobs.get(jid)

    monkeypatch.setattr(service.storage, "get_job", get_job)
    slice1 = service.read_job_log(job_id, 0, 6)
    assert slice1.content == "line1\n"
    assert slice1.next_offset == 6
    jobs[job_id].status = JobStatus.SUCCEEDED
    slice2 = service.read_job_log(job_id, 6, 12)
    assert slice2.content == "line2\n"
    assert slice2.status == JobStatus.SUCCEEDED
