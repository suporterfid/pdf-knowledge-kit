"""Database helpers for ingestion.

This module wraps common SQL operations for sources, ingestion jobs,
documents and chunks. It keeps ingestion code focused on I/O and
embedding while centralizing persistence logic here.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Iterable, Optional, Sequence
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .models import ChunkMetadata, DocumentVersion, Job, JobStatus, Source, SourceType


def _encode_credentials(
    credentials: Any | None,
    *,
    encrypt: Callable[[bytes], bytes] | None = None,
) -> bytes | None:
    """Serialize credentials to bytes with optional encryption."""

    if credentials is None:
        return None
    if isinstance(credentials, bytes):
        raw = credentials
    elif isinstance(credentials, memoryview):
        raw = bytes(credentials)
    elif isinstance(credentials, str):
        raw = credentials.encode("utf-8")
    else:
        raw = json.dumps(credentials).encode("utf-8")
    return encrypt(raw) if encrypt else raw


def _decode_credentials(
    data: Any | None,
    *,
    decrypt: Callable[[bytes], bytes] | None = None,
) -> Any | None:
    """Decode credential payloads using optional decryption and JSON parsing."""

    if data is None:
        return None
    if isinstance(data, memoryview):
        payload = bytes(data)
    elif isinstance(data, (bytes, bytearray)):
        payload = bytes(data)
    else:
        # Already decoded (e.g., plain text from legacy rows)
        payload = str(data).encode("utf-8")
    if decrypt:
        payload = decrypt(payload)
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        try:
            return payload.decode("utf-8")
        except Exception:
            return payload


def _jsonb_or_none(value: Any | None) -> Jsonb | None:
    if value is None or isinstance(value, Jsonb):
        return value
    return Jsonb(value)


def _as_bytes(value: Any | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def _normalize_sync_state(value: Any | None) -> Any | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, memoryview):
        payload = bytes(value)
    elif isinstance(value, (bytes, bytearray)):
        payload = bytes(value)
    else:
        payload = str(value).encode("utf-8")
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return payload


def get_or_create_source(
    conn: psycopg.Connection,
    *,
    type: SourceType,
    path: str | None = None,
    url: str | None = None,
    label: str | None = None,
    location: str | None = None,
    active: bool | None = None,
    params: dict | None = None,
    connector_type: str | None = None,
    credentials: Any | None = None,
    sync_state: dict | None = None,
    version: int | None = None,
    encrypt_credentials: Callable[[bytes], bytes] | None = None,
) -> UUID:
    """Fetch an existing source or create a new record.

    A source is considered unique by its ``path`` or ``url``. Soft deleted
    sources are ignored when checking for existing records.
    """

    with conn.transaction():
        with conn.cursor() as cur:
            update_kwargs: dict[str, Any] = {}
            if label is not None:
                update_kwargs["label"] = label
            if location is not None:
                update_kwargs["location"] = location
            if active is not None:
                update_kwargs["active"] = active
            if params is not None:
                update_kwargs["params"] = params
            if connector_type is not None:
                update_kwargs["connector_type"] = connector_type
            if credentials is not None:
                update_kwargs["credentials"] = credentials
            if sync_state is not None:
                update_kwargs["sync_state"] = sync_state
            if version is not None:
                update_kwargs["version"] = version

            if path is not None:
                cur.execute(
                    "SELECT id FROM sources WHERE path = %s AND deleted_at IS NULL",
                    (path,),
                )
                row = cur.fetchone()
                if row:
                    source_id = row[0]
                    if update_kwargs:
                        update_source(
                            conn,
                            source_id,
                            encrypt_credentials=encrypt_credentials,
                            **update_kwargs,
                        )
                    return source_id

            if url is not None:
                cur.execute(
                    "SELECT id FROM sources WHERE url = %s AND deleted_at IS NULL",
                    (url,),
                )
                row = cur.fetchone()
                if row:
                    source_id = row[0]
                    if update_kwargs:
                        update_source(
                            conn,
                            source_id,
                            encrypt_credentials=encrypt_credentials,
                            **update_kwargs,
                        )
                    return source_id

            source_id = uuid4()
            cur.execute(
                """
                INSERT INTO sources (
                    id,
                    type,
                    path,
                    url,
                    label,
                    location,
                    active,
                    params,
                    connector_type,
                    credentials,
                    sync_state,
                    version,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (
                    source_id,
                    type.value,
                    path,
                    url,
                    label,
                    location,
                    active if active is not None else True,
                    Jsonb(params) if params is not None else None,
                    connector_type,
                    _encode_credentials(credentials, encrypt=encrypt_credentials),
                    _jsonb_or_none(sync_state),
                    version or 1,
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
    decrypt_credentials: Callable[[bytes], bytes] | None = None,
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
        "SELECT id, type, label, location, path, url, active, params, connector_type, credentials, sync_state, version, created_at "
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
            connector_type=row[8],
            credentials=_decode_credentials(row[9], decrypt=decrypt_credentials),
            sync_state=_normalize_sync_state(row[10]),
            version=row[11] or 1,
            created_at=row[12],
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
    connector_type: str | None = None,
    credentials: Any | None = None,
    sync_state: dict | None = None,
    version: int | None = None,
    encrypt_credentials: Callable[[bytes], bytes] | None = None,
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
    if connector_type is not None:
        fields.append(sql.SQL("connector_type = %s"))
        values.append(connector_type)
    if credentials is not None:
        fields.append(sql.SQL("credentials = %s"))
        values.append(_encode_credentials(credentials, encrypt=encrypt_credentials))
    if sync_state is not None:
        fields.append(sql.SQL("sync_state = %s"))
        values.append(_jsonb_or_none(sync_state))
    if version is not None:
        fields.append(sql.SQL("version = %s"))
        values.append(version)

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


def upsert_document(
    conn: psycopg.Connection,
    *,
    path: str,
    bytes_len: int | None = None,
    page_count: int | None = None,
    source_id: UUID | None = None,
    connector_type: str | None = None,
    credentials: Any | None = None,
    sync_state: dict | None = None,
    encrypt_credentials: Callable[[bytes], bytes] | None = None,
    decrypt_credentials: Callable[[bytes], bytes] | None = None,
) -> DocumentVersion:
    """Insert or update a document row and persist a version snapshot."""

    encoded_credentials = _encode_credentials(credentials, encrypt=encrypt_credentials)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, version, source_id, connector_type, credentials, sync_state, bytes, page_count
                FROM documents
                WHERE path = %s
                FOR UPDATE
                """,
                (path,),
            )
            row = cur.fetchone()

            if row:
                (
                    doc_id,
                    current_version,
                    existing_source_id,
                    existing_connector_type,
                    existing_credentials,
                    existing_sync_state,
                    existing_bytes,
                    existing_page_count,
                ) = row
                new_version = (current_version or 0) + 1
                next_source_id = source_id if source_id is not None else existing_source_id
                next_connector_type = (
                    connector_type if connector_type is not None else existing_connector_type
                )
                next_credentials = (
                    encoded_credentials if credentials is not None else _as_bytes(existing_credentials)
                )
                next_sync_state = sync_state if sync_state is not None else existing_sync_state
                next_bytes = bytes_len if bytes_len is not None else existing_bytes
                next_page_count = page_count if page_count is not None else existing_page_count

                if next_connector_type is None and next_source_id is not None:
                    cur.execute(
                        "SELECT connector_type FROM sources WHERE id = %s",
                        (next_source_id,),
                    )
                    src_row = cur.fetchone()
                    if src_row and src_row[0]:
                        next_connector_type = src_row[0]

                cur.execute(
                    """
                    UPDATE documents
                    SET bytes = %s,
                        page_count = %s,
                        source_id = %s,
                        connector_type = %s,
                        credentials = %s,
                        sync_state = %s,
                        version = %s
                    WHERE id = %s
                    """,
                    (
                        next_bytes,
                        next_page_count,
                        next_source_id,
                        next_connector_type,
                        next_credentials,
                        _jsonb_or_none(next_sync_state),
                        new_version,
                        doc_id,
                    ),
                )
            else:
                doc_id = uuid4()
                new_version = 1
                next_source_id = source_id
                next_connector_type = connector_type
                next_credentials = encoded_credentials
                next_sync_state = sync_state
                next_bytes = bytes_len
                next_page_count = page_count

                if next_connector_type is None and next_source_id is not None:
                    cur.execute(
                        "SELECT connector_type FROM sources WHERE id = %s",
                        (next_source_id,),
                    )
                    src_row = cur.fetchone()
                    if src_row and src_row[0]:
                        next_connector_type = src_row[0]

                cur.execute(
                    """
                    INSERT INTO documents (
                        id,
                        path,
                        bytes,
                        page_count,
                        source_id,
                        connector_type,
                        credentials,
                        sync_state,
                        version,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    (
                        doc_id,
                        path,
                        next_bytes,
                        next_page_count,
                        next_source_id,
                        next_connector_type,
                        next_credentials,
                        _jsonb_or_none(next_sync_state),
                        new_version,
                    ),
                )

            cur.execute(
                """
                INSERT INTO document_versions (
                    document_id,
                    source_id,
                    version,
                    bytes,
                    page_count,
                    connector_type,
                    credentials,
                    sync_state
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, version) DO UPDATE
                SET bytes = EXCLUDED.bytes,
                    page_count = EXCLUDED.page_count,
                    connector_type = EXCLUDED.connector_type,
                    credentials = EXCLUDED.credentials,
                    sync_state = EXCLUDED.sync_state
                RETURNING created_at
                """,
                (
                    doc_id,
                    next_source_id,
                    new_version,
                    next_bytes,
                    next_page_count,
                    next_connector_type,
                    next_credentials,
                    _jsonb_or_none(next_sync_state),
                ),
            )
            created_at = cur.fetchone()[0]

    return DocumentVersion(
        document_id=doc_id,
        source_id=next_source_id,
        version=new_version,
        bytes=next_bytes,
        page_count=next_page_count,
        connector_type=next_connector_type,
        credentials=_decode_credentials(next_credentials, decrypt=decrypt_credentials),
        sync_state=_normalize_sync_state(next_sync_state),
        created_at=created_at,
    )


def insert_chunks(
    conn: psycopg.Connection,
    *,
    document_id: UUID,
    chunks: Sequence[str],
    embeddings: Sequence[Sequence[float]],
    metadatas: Sequence[ChunkMetadata],
) -> None:
    """Insert chunk rows ensuring metadata is persisted as JSONB."""

    with conn.transaction():
        with conn.cursor() as cur:
            for index, (content, embedding, metadata) in enumerate(
                zip(chunks, embeddings, metadatas)
            ):
                cur.execute(
                    """
                    INSERT INTO chunks (doc_id, chunk_index, content, token_est, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id, chunk_index) DO UPDATE
                    SET content = EXCLUDED.content,
                        token_est = EXCLUDED.token_est,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        document_id,
                        index,
                        content,
                        int(len(content) / 4) if content else 0,
                        _jsonb_or_none(metadata.to_json()),
                        embedding,
                    ),
                )


def update_source_sync_state(
    conn: psycopg.Connection,
    source_id: UUID,
    *,
    sync_state: dict | None,
    version: int | None = None,
) -> None:
    """Update the stored sync cursor/state for a connector source."""

    fields: list[sql.SQL] = [sql.SQL("sync_state = %s")]
    values: list[Any] = [_jsonb_or_none(sync_state)]
    if version is not None:
        fields.append(sql.SQL("version = %s"))
        values.append(version)

    query = sql.SQL("UPDATE sources SET {fields}, updated_at = now() WHERE id = %s").format(
        fields=sql.SQL(", ").join(fields)
    )
    values.append(source_id)

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(query, values)


def get_latest_versions_for_connector(
    conn: psycopg.Connection,
    *,
    connector_type: str,
    source_id: UUID | None = None,
    decrypt_credentials: Callable[[bytes], bytes] | None = None,
) -> Iterable[DocumentVersion]:
    """Yield the latest document version entries for a given connector."""

    query = """
        SELECT dv.document_id,
               dv.source_id,
               dv.version,
               dv.bytes,
               dv.page_count,
               dv.connector_type,
               dv.credentials,
               dv.sync_state,
               dv.created_at
        FROM document_versions dv
        JOIN (
            SELECT document_id, MAX(version) AS max_version
            FROM document_versions
            GROUP BY document_id
        ) latest ON latest.document_id = dv.document_id AND latest.max_version = dv.version
        JOIN documents d ON d.id = dv.document_id
        WHERE d.connector_type = %s
    """
    params: list[Any] = [connector_type]
    if source_id is not None:
        query += " AND dv.source_id = %s"
        params.append(source_id)

    with conn.cursor() as cur:
        cur.execute(query, params)
        for row in cur.fetchall():
            yield DocumentVersion(
                document_id=row[0],
                source_id=row[1],
                version=row[2],
                bytes=row[3],
                page_count=row[4],
                connector_type=row[5],
                credentials=_decode_credentials(row[6], decrypt=decrypt_credentials),
                sync_state=_normalize_sync_state(row[7]),
                created_at=row[8],
            )

