"""Database helpers for ingestion."""
from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID, uuid4

import psycopg

from .models import IngestionJob, IngestionJobStatus, Source, SourceType


def create_source(conn: psycopg.Connection, *, type: SourceType, path: str | None = None, url: str | None = None) -> UUID:
    source_id = uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sources (id, type, path, url, created_at) VALUES (%s, %s, %s, %s, now())",
            (source_id, type.value, path, url),
        )
    conn.commit()
    return source_id


def get_source(conn: psycopg.Connection, source_id: UUID) -> Optional[Source]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, type, path, url, created_at FROM sources WHERE id = %s", (source_id,))
        row = cur.fetchone()
    if not row:
        return None
    return Source(
        id=row[0],
        type=SourceType(row[1]),
        path=row[2],
        url=row[3],
        created_at=row[4],
    )


def list_sources(conn: psycopg.Connection) -> Iterable[Source]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, type, path, url, created_at FROM sources ORDER BY created_at DESC")
        rows = cur.fetchall()
    for row in rows:
        yield Source(
            id=row[0],
            type=SourceType(row[1]),
            path=row[2],
            url=row[3],
            created_at=row[4],
        )


def create_job(conn: psycopg.Connection, source_id: UUID, status: IngestionJobStatus = IngestionJobStatus.PENDING) -> UUID:
    job_id = uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingestion_jobs (id, source_id, status, created_at) VALUES (%s, %s, %s, now())",
            (job_id, source_id, status.value),
        )
    conn.commit()
    return job_id


def update_job_status(
    conn: psycopg.Connection, job_id: UUID, status: IngestionJobStatus, error: str | None = None
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion_jobs SET status = %s, error = %s, updated_at = now() WHERE id = %s",
            (status.value, error, job_id),
        )
    conn.commit()


def get_job(conn: psycopg.Connection, job_id: UUID) -> Optional[IngestionJob]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, source_id, status, created_at, updated_at, error FROM ingestion_jobs WHERE id = %s",
            (job_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return IngestionJob(
        id=row[0],
        source_id=row[1],
        status=IngestionJobStatus(row[2]),
        created_at=row[3],
        updated_at=row[4],
        error=row[5],
    )


def list_jobs(conn: psycopg.Connection) -> Iterable[IngestionJob]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, source_id, status, created_at, updated_at, error FROM ingestion_jobs ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
    for row in rows:
        yield IngestionJob(
            id=row[0],
            source_id=row[1],
            status=IngestionJobStatus(row[2]),
            created_at=row[3],
            updated_at=row[4],
            error=row[5],
        )
