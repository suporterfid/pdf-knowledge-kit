"""Pydantic models and enums for ingestion jobs."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class SourceType(str, Enum):
    """Type of source being ingested."""

    LOCAL = "local"
    URL = "url"


class IngestionJobStatus(str, Enum):
    """Lifecycle status for an ingestion job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Source(BaseModel):
    id: UUID
    type: SourceType
    path: Optional[str] = None
    url: Optional[HttpUrl] = None
    created_at: datetime


class IngestionJob(BaseModel):
    id: UUID
    source_id: UUID
    status: IngestionJobStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    error: Optional[str] = None


class JobLogSlice(BaseModel):
    """A slice of a job log file.

    Attributes
    ----------
    text:
        The log content read starting at ``offset``.
    next_offset:
        Byte offset for the next read.
    total:
        Total size of the log file in bytes.
    status:
        Final status of the job if it has completed, otherwise ``None``.
    """

    text: str
    next_offset: int
    total: int
    status: Optional[IngestionJobStatus] = None
