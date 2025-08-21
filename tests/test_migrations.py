import os
from pathlib import Path

import psycopg
import pytest

from app.ingestion import service, storage
from app.ingestion.models import JobStatus, SourceType


def _require_conn():
    url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    try:
        return psycopg.connect(url)
    except Exception:
        pytest.skip("database not available")


def test_migration_persistence_and_soft_delete(tmp_path):
    conn = _require_conn()
    service.reset_schema(conn, Path("schema.sql"), Path("migrations"))
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
    src_id = storage.get_or_create_source(conn, type=SourceType.LOCAL_DIR, path=str(tmp_path / "a"))
    job_id = storage.create_job(conn, src_id)
    job = storage.get_job(conn, job_id)
    assert job and job.status == JobStatus.QUEUED
    storage.soft_delete_source(conn, src_id)
    assert list(storage.list_sources(conn)) == []
    conn.close()
