from __future__ import annotations

import os
from pathlib import Path
from typing import List
from uuid import UUID

import psycopg
from fastapi import APIRouter, Body, Depends, HTTPException
from ..ingestion import service, storage
from ..ingestion.models import IngestionJobStatus, SourceType, JobLogSlice
from ..security.auth import require_role

router = APIRouter(prefix="/api/admin/ingest", tags=["admin-ingest"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/local")
def start_local_job(
    path: str,
    use_ocr: bool = False,
    ocr_lang: str | None = None,
    role: str = Depends(require_role("operator")),
):
    job_id = service.ingest_local(Path(path), use_ocr=use_ocr, ocr_lang=ocr_lang)
    return {"job_id": str(job_id)}


@router.post("/jobs/url")
def start_url_job(
    url: str,
    role: str = Depends(require_role("operator")),
):
    job_id = service.ingest_url(url)
    return {"job_id": str(job_id)}


@router.post("/jobs/urls")
def start_urls_job(
    urls: List[str] = Body(...),
    role: str = Depends(require_role("operator")),
):
    job_id = service.ingest_urls(urls)
    return {"job_id": str(job_id)}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: UUID, role: str = Depends(require_role("operator"))):
    service.cancel_job(job_id)
    return {"status": "canceled"}


@router.get("/jobs")
def list_jobs(role: str = Depends(require_role("viewer"))):
    return service.list_jobs()


@router.get("/sources")
def list_sources(role: str = Depends(require_role("viewer"))):
    with _get_conn() as conn:
        return list(storage.list_sources(conn))


@router.post("/sources")
def create_source(
    type: SourceType,
    path: str | None = None,
    url: str | None = None,
    role: str = Depends(require_role("operator")),
):
    with _get_conn() as conn:
        source_id = storage.get_or_create_source(
            conn, type=type, path=path, url=url
        )
    return {"source_id": str(source_id)}


@router.put("/sources/{source_id}")
def update_source(
    source_id: UUID,
    path: str | None = None,
    url: str | None = None,
    role: str = Depends(require_role("operator")),
):
    with _get_conn() as conn:
        storage.update_source(conn, source_id, path=path, url=url)
    return {"status": "updated"}


@router.delete("/sources/{source_id}")
def delete_source(
    source_id: UUID, role: str = Depends(require_role("operator"))
):
    with _get_conn() as conn:
        storage.soft_delete_source(conn, source_id)
    return {"status": "deleted"}


@router.post("/sources/{source_id}/reindex")
def reindex_source_endpoint(
    source_id: UUID, role: str = Depends(require_role("operator"))
):
    service.reindex_source(source_id)
    return {"status": "reindexing"}


@router.get("/jobs/{job_id}/logs", response_model=JobLogSlice)
def get_job_logs(
    job_id: UUID,
    offset: int = 0,
    limit: int = 16_384,
    role: str = Depends(require_role("viewer")),
):
    """Return a slice of the job log starting at ``offset``."""

    return service.read_job_log(job_id, offset=offset, limit=limit)
