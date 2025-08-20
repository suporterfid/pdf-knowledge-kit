"""Database helpers for ingestion."""
from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID, uuid4

import psycopg

from .models import IngestionJob, IngestionJobStatus, Source, SourceType


def get_or_create_source(
    conn: psycopg.Connection,
    *,
    type: SourceType,
    path: str | None = None,
    url: str | None = None,
) -> UUID:
    """Fetch an existing source or create a new record.

    A source is considered unique by its ``path`` or ``url``. Soft deleted
    sources are ignored when checking for existing records.
    """

    with conn.cursor() as cur:
        # Try to find an existing source first.
        if path is not None:
            cur.execute(
                "SELECT id FROM sources WHERE path = %s AND deleted_at IS NULL",
                (path,),
            )
            row = cur.fetchone()
            if row:
                return row[0]

        if url is not None:
            cur.execute(
                "SELECT id FROM sources WHERE url = %s AND deleted_at IS NULL",
                (url,),
            )
            row = cur.fetchone()
            if row:
                return row[0]

        # No existing source found; create one.
        source_id = uuid4()
        cur.execute(
            "INSERT INTO sources (id, type, path, url, created_at) VALUES (%s, %s, %s, %s, now())",
            (source_id, type.value, path, url),
        )

    conn.commit()
    return source_id


def list_sources(conn: psycopg.Connection) -> Iterable[Source]:
    """Return active (non-deleted) sources ordered by creation date."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, type, path, url, created_at FROM sources WHERE deleted_at IS NULL ORDER BY created_at DESC"
        )
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


def update_source(
    conn: psycopg.Connection,
    source_id: UUID,
    *,
    path: str | None = None,
    url: str | None = None,
) -> None:
    """Update a source's path or URL."""

    fields: list[str] = []
    values: list[str] = []
    if path is not None:
        fields.append("path = %s")
        values.append(path)
    if url is not None:
        fields.append("url = %s")
        values.append(url)
    if not fields:
        return

    values.append(source_id)
    sql = f"UPDATE sources SET {', '.join(fields)}, updated_at = now() WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, values)
    conn.commit()


def soft_delete_source(conn: psycopg.Connection, source_id: UUID) -> None:
    """Soft delete a source by marking its ``deleted_at`` timestamp."""

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sources SET deleted_at = now(), updated_at = now() WHERE id = %s",
            (source_id,),
        )
    conn.commit()
