"""Pydantic models and enums for ingestion jobs and sources."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, HttpUrl


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """Types of sources that may be ingested."""

    LOCAL_DIR = "local_dir"
    URL = "url"
    URL_LIST = "url_list"


class JobStatus(str, Enum):
    """Lifecycle status values for an ingestion job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class LocalIngestRequest(BaseModel):
    """Request model for ingesting a local directory."""

    path: str
    use_ocr: bool = False
    ocr_lang: str | None = None


class UrlIngestRequest(BaseModel):
    """Request model for ingesting a single URL."""

    url: HttpUrl


class UrlsIngestRequest(BaseModel):
    """Request model for ingesting multiple URLs."""

    urls: List[HttpUrl]


class ReindexRequest(BaseModel):
    """Request to re-index an existing source."""

    source_id: UUID


class SourceCreate(BaseModel):
    """Model used to create a new source record."""

    type: SourceType
    path: str | None = None
    url: HttpUrl | None = None
    label: str | None = None
    location: str | None = None
    active: bool = True
    params: dict | None = None
    connector_type: str | None = None
    credentials: Any | None = None
    sync_state: dict | None = None
    version: int | None = None


class SourceUpdate(BaseModel):
    """Model used to update an existing source record."""

    path: str | None = None
    url: HttpUrl | None = None
    label: str | None = None
    location: str | None = None
    active: bool | None = None
    params: dict | None = None
    connector_type: str | None = None
    credentials: Any | None = None
    sync_state: dict | None = None
    version: int | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class JobCreated(BaseModel):
    """Response returned when a job is created."""

    job_id: UUID


class Source(BaseModel):
    id: UUID
    type: SourceType
    label: str | None = None
    location: str | None = None
    path: str | None = None
    url: HttpUrl | None = None
    active: bool = True
    params: dict | None = None
    connector_type: str | None = None
    credentials: Any | None = None
    sync_state: dict | None = None
    version: int = 1
    created_at: datetime


class Job(BaseModel):
    id: UUID
    source_id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime | None = None
    error: str | None = None
    log_path: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobSummary(BaseModel):
    """A lightweight summary of a job."""

    id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime | None = None


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    """Generic container for list responses."""

    items: List[T]
    total: int


class JobLogSlice(BaseModel):
    """A slice of a job's log output."""

    content: str
    next_offset: int
    status: JobStatus | None = None


class ChunkMetadata(BaseModel):
    """Structured representation of the metadata stored alongside chunks."""

    source_path: str
    mime_type: str
    page_number: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    extra: Dict[str, Any] | None = None

    def to_json(self) -> Dict[str, Any]:
        """Return a JSON-serialisable payload for persistence."""

        payload: Dict[str, Any] = {
            "source_path": self.source_path,
            "mime_type": self.mime_type,
            "page_number": self.page_number,
            "sheet_name": self.sheet_name,
            "row_number": self.row_number,
        }
        if self.extra:
            payload.update(self.extra)
        return {k: v for k, v in payload.items() if v is not None}


class DocumentVersion(BaseModel):
    """Snapshot of a document's metadata for version history APIs."""

    document_id: UUID
    source_id: UUID | None = None
    version: int
    bytes: int | None = None
    page_count: int | None = None
    connector_type: str | None = None
    credentials: Any | None = None
    sync_state: dict | None = None
    created_at: datetime

