from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..ingestion import service, storage
from ..ingestion.models import IngestionJobStatus
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


@router.get("/jobs/{job_id}/logs")
async def stream_logs(job_id: UUID, role: str = Depends(require_role("viewer"))):
    async def event_generator():
        last_size = 0
        while True:
            await asyncio.sleep(0.5)
            log = service.read_job_log(job_id)
            if len(log) > last_size:
                yield {"data": log[last_size:]}
                last_size = len(log)
            job = service.get_job(job_id)
            if job and job.status in (
                IngestionJobStatus.COMPLETED,
                IngestionJobStatus.FAILED,
                IngestionJobStatus.CANCELED,
            ):
                yield {"event": "end", "data": job.status}
                break
    return EventSourceResponse(event_generator())
