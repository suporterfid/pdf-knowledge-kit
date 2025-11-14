import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# ruff: noqa: S101
import psycopg
import pytest
from app.ingestion import service, storage
from app.ingestion.models import JobStatus, SourceType


def _set_tenant(conn: psycopg.Connection, tenant_id):
    with conn.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", (str(tenant_id),))


def _get_conn(*, tenant_id=None):
    url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    try:
        conn = psycopg.connect(url)
    except Exception:
        pytest.skip("database not available")
    if tenant_id is not None:
        _set_tenant(conn, tenant_id)
    return conn


def test_storage_sources_and_jobs(tmp_path):
    tenant_a = uuid4()
    tenant_b = uuid4()
    conn = _get_conn()
    service.reset_schema(conn, Path("schema.sql"), Path("migrations"))
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS path TEXT")
        cur.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS url TEXT")
        cur.execute(
            "ALTER TABLE sources ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"
        )
        cur.execute("ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS log_path TEXT")
        cur.execute(
            "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ"
        )
        cur.execute(
            "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ"
        )
        cur.execute(
            "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()"
        )
        cur.execute(
            "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"
        )
    conn.commit()

    _set_tenant(conn, tenant_a)
    src_id = storage.get_or_create_source(
        conn,
        tenant_id=tenant_a,
        type=SourceType.URL,
        url="http://a",
    )
    src_id2 = storage.get_or_create_source(
        conn,
        tenant_id=tenant_a,
        type=SourceType.LOCAL_DIR,
        path=str(tmp_path / "b"),
    )

    _set_tenant(conn, tenant_b)
    other_src = storage.get_or_create_source(
        conn,
        tenant_id=tenant_b,
        type=SourceType.URL,
        url="http://other",
    )

    _set_tenant(conn, tenant_a)
    sources = list(storage.list_sources(conn, tenant_id=tenant_a, active=True))
    assert len(sources) == 2
    assert {s.id for s in sources} == {src_id, src_id2}

    storage.update_source(conn, src_id, tenant_id=tenant_a, label="first")
    updated = list(storage.list_sources(conn, tenant_id=tenant_a, type=SourceType.URL))[
        0
    ]
    assert updated.label == "first"

    job_id = storage.create_job(conn, tenant_id=tenant_a, source_id=src_id)
    storage.update_job_status(
        conn,
        job_id,
        tenant_id=tenant_a,
        status=JobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    job = storage.get_job(conn, job_id, tenant_id=tenant_a)
    assert job and job.status == JobStatus.RUNNING

    jobs = list(storage.list_jobs(conn, tenant_id=tenant_a, status=JobStatus.RUNNING))
    assert len(jobs) == 1

    _set_tenant(conn, tenant_b)
    jobs_other = list(storage.list_jobs(conn, tenant_id=tenant_b))
    assert jobs_other == []

    storage.update_job_status(
        conn,
        job_id,
        tenant_id=tenant_a,
        status=JobStatus.SUCCEEDED,
        finished_at=datetime.now(timezone.utc),
    )
    storage.soft_delete_source(conn, src_id, tenant_id=tenant_a)
    remaining = list(storage.list_sources(conn, tenant_id=tenant_a, active=None))
    assert len(remaining) == 1 and remaining[0].id == src_id2

    _set_tenant(conn, tenant_b)
    other_sources = list(storage.list_sources(conn, tenant_id=tenant_b))
    assert len(other_sources) == 1 and other_sources[0].id == other_src
    conn.close()
