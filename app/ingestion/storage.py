"""Database helpers for ingestion.

This module wraps common SQL operations for sources, ingestion jobs,
documents and chunks. It keeps ingestion code focused on I/O and
embedding while centralizing persistence logic here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .models import Job, JobStatus, Source, SourceType


def get_or_create_source(
    conn: psycopg.Connection,
    *,
    type: SourceType,
    path: str | None = None,
    url: str | None = None,
    label: str | None = None,
    location: str | None = None,
    active: bool = True,
    params: dict | None = None,
) -> UUID:
    """Fetch an existing source or create a new record.

    A source is considered unique by its ``path`` or ``url``. Soft deleted
    sources are ignored when checking for existing records.
    """

    with conn.transaction():
        with conn.cursor() as cur:
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

            source_id = uuid4()
            cur.execute(
                """
                INSERT INTO sources (id, type, path, url, label, location, active, params, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (
                    source_id,
                    type.value,
                    path,
                    url,
                    label,
                    location,
                    active,
                    Jsonb(params) if params is not None else None,
                ),
            )
            return source_id


def list_sources(
    conn: psycopg.Connection,
    *,
    active: Optional[bool] = True,
    type: SourceType | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> Iterable[Source]:
    """Return sources ordered by creation date with optional filters."""

    conditions = ["deleted_at IS NULL"]
    params: list = []
    if active is not None:
        conditions.append("active = %s")
        params.append(active)
    if type is not None:
        conditions.append("type = %s")
        params.append(type.value if isinstance(type, SourceType) else type)

    query = (
        "SELECT id, type, label, location, path, url, active, params, created_at "
        "FROM sources WHERE " + " AND ".join(conditions) + " ORDER BY created_at DESC"
    )
    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)
    if offset:
        query += " OFFSET %s"
        params.append(offset)

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    for row in rows:
        yield Source(
            id=row[0],
            type=SourceType(row[1]),
            label=row[2],
            location=row[3],
            path=row[4],
            url=row[5],
            active=row[6],
            params=row[7],
            created_at=row[8],
        )


def create_job(
    conn: psycopg.Connection,
    source_id: UUID,
    status: JobStatus = JobStatus.QUEUED,
) -> UUID:
    """Create a new ingestion job for a given source and return its id."""
    job_id = uuid4()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingestion_jobs (id, source_id, status, created_at) VALUES (%s, %s, %s, now())",
                (job_id, source_id, status.value),
            )
    return job_id


def update_job_status(
    conn: psycopg.Connection,
    job_id: UUID,
    status: JobStatus,
    *,
    error: str | None = None,
    log_path: str | None = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> None:
    """Update job state and optional metadata."""

    fields = [sql.SQL("status = %s"), sql.SQL("updated_at = now()")] 
    values: list = [status.value]
    if error is not None:
        fields.append(sql.SQL("error = %s"))
        values.append(error)
    if log_path is not None:
        fields.append(sql.SQL("log_path = %s"))
        values.append(log_path)
    if started_at is not None:
        fields.append(sql.SQL("started_at = %s"))
        values.append(started_at)
    if finished_at is not None:
        fields.append(sql.SQL("finished_at = %s"))
        values.append(finished_at)

    query = sql.SQL("UPDATE ingestion_jobs SET {fields} WHERE id = %s").format(
        fields=sql.SQL(", ").join(fields)
    )
    values.append(job_id)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(query, values)


def get_job(conn: psycopg.Connection, job_id: UUID) -> Optional[Job]:
    """Return a single job by id or ``None`` if not found."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source_id, status, created_at, updated_at, error, log_path, started_at, finished_at
            FROM ingestion_jobs WHERE id = %s
            """,
            (job_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return Job(
        id=row[0],
        source_id=row[1],
        status=JobStatus(row[2]),
        created_at=row[3],
        updated_at=row[4],
        error=row[5],
        log_path=row[6],
        started_at=row[7],
        finished_at=row[8],
    )


def list_jobs(
    conn: psycopg.Connection,
    *,
    status: JobStatus | None = None,
    source_id: UUID | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> Iterable[Job]:
    """List jobs with optional filters."""

    conditions = []
    params: list = []
    if status is not None:
        conditions.append("status = %s")
        params.append(status.value if isinstance(status, JobStatus) else status)
    if source_id is not None:
        conditions.append("source_id = %s")
        params.append(source_id)

    query = (
        "SELECT id, source_id, status, created_at, updated_at, error, log_path, started_at, finished_at "
        "FROM ingestion_jobs"
    )
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)
    if offset:
        query += " OFFSET %s"
        params.append(offset)

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    for row in rows:
        yield Job(
            id=row[0],
            source_id=row[1],
            status=JobStatus(row[2]),
            created_at=row[3],
            updated_at=row[4],
            error=row[5],
            log_path=row[6],
            started_at=row[7],
            finished_at=row[8],
        )


def update_source(
    conn: psycopg.Connection,
    source_id: UUID,
    *,
    path: str | None = None,
    url: str | None = None,
    label: str | None = None,
    location: str | None = None,
    active: bool | None = None,
    params: dict | None = None,
) -> None:
    """Update fields for a source (partial update)."""

    fields: list[sql.SQL] = []
    values: list = []
    if path is not None:
        fields.append(sql.SQL("path = %s"))
        values.append(path)
    if url is not None:
        fields.append(sql.SQL("url = %s"))
        values.append(url)
    if label is not None:
        fields.append(sql.SQL("label = %s"))
        values.append(label)
    if location is not None:
        fields.append(sql.SQL("location = %s"))
        values.append(location)
    if active is not None:
        fields.append(sql.SQL("active = %s"))
        values.append(active)
    if params is not None:
        fields.append(sql.SQL("params = %s"))
        values.append(Jsonb(params))

    if not fields:
        return

    fields.append(sql.SQL("updated_at = now()"))
    query = sql.SQL("UPDATE sources SET {fields} WHERE id = %s").format(
        fields=sql.SQL(", ").join(fields)
    )
    values.append(source_id)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(query, values)


def soft_delete_source(conn: psycopg.Connection, source_id: UUID) -> None:
    """Soft delete a source (mark deleted_at and set active=false)."""

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sources SET active = FALSE, deleted_at = now(), updated_at = now() WHERE id = %s",
                (source_id,),
            )

