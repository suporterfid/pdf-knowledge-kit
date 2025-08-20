"""Pydantic models and enums for ingestion jobs and sources."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar
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


class SourceUpdate(BaseModel):
    """Model used to update an existing source record."""

    path: str | None = None
    url: HttpUrl | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class JobCreated(BaseModel):
    """Response returned when a job is created."""

    job_id: UUID


class Source(BaseModel):
    id: UUID
    type: SourceType
    path: str | None = None
    url: HttpUrl | None = None
    created_at: datetime


class Job(BaseModel):
    id: UUID
    source_id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime | None = None
    error: str | None = None


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

