import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from app.ingestion import service, storage
from app.ingestion.models import JobStatus, SourceType


def _get_conn():
    url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    try:
        return psycopg.connect(url)
    except Exception:
        pytest.skip("database not available")


def test_storage_sources_and_jobs(tmp_path):
    conn = _get_conn()
    service.ensure_schema(conn, Path("schema.sql"), Path("migrations"))
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS path TEXT")
        cur.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS url TEXT")
        cur.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS log_path TEXT")
        cur.execute("ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()")
        cur.execute("ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    conn.commit()

    src_id = storage.get_or_create_source(conn, type=SourceType.URL, url="http://a")
    src_id2 = storage.get_or_create_source(conn, type=SourceType.LOCAL_DIR, path=str(tmp_path / "b"))

    sources = list(storage.list_sources(conn, active=True))
    assert len(sources) == 2

    storage.update_source(conn, src_id, label="first")
    updated = list(storage.list_sources(conn, type=SourceType.URL))[0]
    assert updated.label == "first"

    job_id = storage.create_job(conn, src_id)
    storage.update_job_status(conn, job_id, JobStatus.RUNNING, started_at=datetime.utcnow())
    job = storage.get_job(conn, job_id)
    assert job and job.status == JobStatus.RUNNING

    jobs = list(storage.list_jobs(conn, status=JobStatus.RUNNING))
    assert len(jobs) == 1

    storage.update_job_status(conn, job_id, JobStatus.SUCCEEDED, finished_at=datetime.utcnow())
    storage.soft_delete_source(conn, src_id)
    remaining = list(storage.list_sources(conn))
    assert len(remaining) == 1 and remaining[0].id == src_id2
    conn.close()
