from __future__ import annotations

"""Admin ingestion API using Pydantic models."""

import os
from pathlib import Path
from typing import List
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..ingestion import service, storage
from ..ingestion.models import (
    Job,
    JobCreated,
    JobLogSlice,
    JobStatus,
    ListResponse,
    LocalIngestRequest,
    Source,
    SourceCreate,
    SourceType,
    SourceUpdate,
    UrlIngestRequest,
    UrlsIngestRequest,
)
from ..security.auth import require_role

router = APIRouter(prefix="/api/admin/ingest", tags=["admin-ingest"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    """Return a new database connection or raise HTTP 500."""
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _fetch_source(conn: psycopg.Connection, source_id: UUID) -> Source:
    for src in storage.list_sources(conn, active=None):
        if src.id == source_id:
            return src
    raise HTTPException(status_code=404, detail="Source not found")


@router.post("/local", response_model=JobCreated)
def start_local_job(
    req: LocalIngestRequest,
    role: str = Depends(require_role("operator")),
) -> JobCreated:
    job_id = service.ingest_local(
        Path(req.path), use_ocr=req.use_ocr, ocr_lang=req.ocr_lang
    )
    return JobCreated(job_id=job_id)


@router.post("/url", response_model=JobCreated)
def start_url_job(
    req: UrlIngestRequest,
    role: str = Depends(require_role("operator")),
) -> JobCreated:
    job_id = service.ingest_url(str(req.url))
    return JobCreated(job_id=job_id)


@router.post("/urls", response_model=JobCreated)
def start_urls_job(
    req: UrlsIngestRequest,
    role: str = Depends(require_role("operator")),
) -> JobCreated:
    job_id = service.ingest_urls([str(u) for u in req.urls])
    return JobCreated(job_id=job_id)


@router.get("/jobs", response_model=ListResponse[Job])
def list_jobs(
    status: JobStatus | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    role: str = Depends(require_role("viewer")),
) -> ListResponse[Job]:
    jobs = service.list_jobs()
    if status is not None:
        jobs = [j for j in jobs if j.status == status]
    total = len(jobs)
    if offset:
        jobs = jobs[offset:]
    if limit is not None:
        jobs = jobs[:limit]
    return ListResponse[Job](items=jobs, total=total)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(
    job_id: UUID, role: str = Depends(require_role("viewer"))
) -> Job:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(
    job_id: UUID, role: str = Depends(require_role("operator"))
) -> Job:
    service.cancel_job(job_id)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/logs", response_model=JobLogSlice)
def get_job_logs(
    job_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=16_384, ge=1),
    role: str = Depends(require_role("viewer")),
) -> JobLogSlice:
    """Return a slice of the job log starting at ``offset``."""
    return service.read_job_log(job_id, offset=offset, limit=limit)


@router.get("/sources", response_model=ListResponse[Source])
def list_sources(
    active: bool | None = Query(default=True),
    type: SourceType | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    role: str = Depends(require_role("viewer")),
) -> ListResponse[Source]:
    with _get_conn() as conn:
        all_items = list(
            storage.list_sources(conn, active=active, type=type)
        )
        total = len(all_items)
        items = all_items[offset:]
        if limit is not None:
            items = items[:limit]
        return ListResponse[Source](items=items, total=total)


@router.post("/sources", response_model=Source)
def create_source(
    req: SourceCreate, role: str = Depends(require_role("operator"))
) -> Source:
    with _get_conn() as conn:
        source_id = storage.get_or_create_source(
            conn,
            type=req.type,
            path=req.path,
            url=str(req.url) if req.url else None,
            label=req.label,
            location=req.location,
            active=req.active,
            params=req.params,
        )
        return _fetch_source(conn, source_id)


@router.put("/sources/{source_id}", response_model=Source)
def update_source(
    source_id: UUID,
    req: SourceUpdate,
    role: str = Depends(require_role("operator")),
) -> Source:
    with _get_conn() as conn:
        storage.update_source(
            conn,
            source_id,
            path=req.path,
            url=str(req.url) if req.url else None,
            label=req.label,
            location=req.location,
            active=req.active,
            params=req.params,
        )
        return _fetch_source(conn, source_id)


@router.delete("/sources/{source_id}", response_model=Source)
def delete_source(
    source_id: UUID, role: str = Depends(require_role("operator"))
) -> Source:
    with _get_conn() as conn:
        src = _fetch_source(conn, source_id)
        storage.soft_delete_source(conn, source_id)
        src.active = False
        return src


@router.post("/sources/{source_id}/reindex", response_model=JobCreated)
def reindex_source_endpoint(
    source_id: UUID, role: str = Depends(require_role("operator"))
) -> JobCreated:
    job_id = service.reindex_source(source_id)
    if not job_id:
        raise HTTPException(status_code=404, detail="Source not found")
    return JobCreated(job_id=job_id)
