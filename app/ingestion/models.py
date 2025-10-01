"""Pydantic models and enums for ingestion jobs and sources."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """Types of sources that may be ingested."""

    LOCAL_DIR = "local_dir"
    URL = "url"
    URL_LIST = "url_list"
    DATABASE = "database"
    API = "api"
    AUDIO_TRANSCRIPT = "audio_transcript"
    VIDEO_TRANSCRIPT = "video_transcript"


class DatabaseQueryConfig(TypedDict, total=False):
    """Configuration for a single SQL query executed by the database connector."""

    name: str
    sql: str
    text_column: str
    id_column: str
    cursor_column: str
    cursor_param: str
    initial_cursor: str | int | float | None
    mime_type: str
    document_path_template: str
    params: Dict[str, Any]
    extra_metadata_fields: List[str]


class DatabaseSourceParams(TypedDict, total=False):
    """Expected ``sources.params`` payload for :class:`~SourceType.DATABASE`."""

    dsn: str
    driver: str
    host: str
    port: int
    database: str
    user: str
    queries: List[DatabaseQueryConfig]


class ApiPaginationConfig(TypedDict, total=False):
    """Pagination behaviour for the REST connector."""

    type: str  # "cursor" (default) or "page"
    cursor_param: str
    next_cursor_path: str
    page_param: str
    page_size_param: str
    page_size: int
    start_page: int


class ApiSourceParams(TypedDict, total=False):
    """Expected ``sources.params`` payload for :class:`~SourceType.API`."""

    base_url: str
    endpoint: str
    method: str
    headers: Dict[str, str]
    query_params: Dict[str, Any]
    body: Dict[str, Any]
    pagination: ApiPaginationConfig
    records_path: str
    id_field: str
    text_fields: List[str]
    timestamp_field: str
    mime_type: str
    document_path_template: str


class TranscriptionSourceParams(TypedDict, total=False):
    """Configuration payload for transcription sources."""

    provider: str
    media_uri: str
    cache_dir: str
    cache_key: str
    poll_interval: float
    language: str
    diarization: bool
    whisper_model: str
    whisper_compute_type: str
    aws_region: str
    aws_transcribe_params: Dict[str, Any]
    output_mime_type: str
    extra_metadata: Dict[str, Any]
    segments: List[Dict[str, Any]]
    transcript_text: str
    cache_ttl_seconds: int
    job_name_prefix: str


class ConnectorCredentials(BaseModel):
    """Structured credentials payload supporting inline secrets and references."""

    values: Dict[str, Any] | None = None
    token: str | None = None
    secret_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    def resolved(self) -> Any | None:
        """Return the payload that should be stored with a source/definition."""

        if self.values is not None:
            return self.values
        if self.token is not None:
            return self.token
        return None


class DatabaseQuery(BaseModel):
    """Pydantic representation of :class:`DatabaseQueryConfig`."""

    name: str | None = None
    sql: str
    text_column: str
    id_column: str
    cursor_column: str | None = None
    cursor_param: str | None = Field(default=None, alias="cursor_param")
    initial_cursor: str | int | float | None = None
    mime_type: str | None = None
    document_path_template: str | None = None
    params: Dict[str, Any] | None = None
    extra_metadata_fields: List[str] | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _check_required_fields(self) -> "DatabaseQuery":
        if not self.sql:
            raise ValueError("database query requires 'sql'")
        if not self.text_column:
            raise ValueError("database query requires 'text_column'")
        if not self.id_column:
            raise ValueError("database query requires 'id_column'")
        return self


class DatabaseConnectorParams(BaseModel):
    """Validated payload for database connectors."""

    dsn: str | None = None
    driver: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    queries: List[DatabaseQuery]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _ensure_queries(self) -> "DatabaseConnectorParams":
        if not self.queries:
            raise ValueError("database connector requires at least one query")
        return self


class ApiPagination(BaseModel):
    """Pagination settings for the REST connector."""

    type: str | None = None
    cursor_param: str | None = None
    next_cursor_path: str | None = None
    page_param: str | None = None
    page_size_param: str | None = None
    page_size: int | None = None
    start_page: int | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_type(self) -> "ApiPagination":
        if self.type and self.type not in {"cursor", "page"}:
            raise ValueError("pagination.type must be 'cursor' or 'page'")
        return self


class ApiConnectorParams(BaseModel):
    """Validated payload for REST/API connectors."""

    base_url: str | None = None
    endpoint: str | None = None
    method: str | None = None
    headers: Dict[str, str] | None = None
    query_params: Dict[str, Any] | None = None
    body: Dict[str, Any] | None = None
    pagination: ApiPagination | None = None
    records_path: str | None = None
    id_field: str | None = None
    text_fields: List[str] | None = None
    timestamp_field: str | None = None
    mime_type: str | None = None
    document_path_template: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _ensure_endpoint(self) -> "ApiConnectorParams":
        if not self.endpoint and not self.base_url:
            raise ValueError("API connector requires an endpoint or base_url")
        return self


class TranscriptionConnectorParams(BaseModel):
    """Validated payload for transcription connectors."""

    provider: str
    media_uri: str | None = None
    cache_dir: str | None = None
    cache_key: str | None = None
    poll_interval: float | None = None
    language: str | None = None
    diarization: bool | None = None
    whisper_model: str | None = None
    whisper_compute_type: str | None = None
    aws_region: str | None = None
    aws_transcribe_params: Dict[str, Any] | None = None
    output_mime_type: str | None = None
    extra_metadata: Dict[str, Any] | None = None
    segments: List[Dict[str, Any]] | None = None
    transcript_text: str | None = None
    cache_ttl_seconds: int | None = None
    job_name_prefix: str | None = None

    model_config = ConfigDict(extra="forbid")


class BaseConnectorJobRequest(BaseModel):
    """Common fields for connector-backed ingestion requests."""

    source_id: UUID | None = None
    connector_definition_id: UUID | None = None
    label: str | None = None
    location: str | None = None
    connector_metadata: Dict[str, Any] | None = None
    credentials: ConnectorCredentials | Dict[str, Any] | str | None = None
    sync_state: Dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def _normalise_credentials(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        credentials = values.get("credentials")
        if isinstance(credentials, ConnectorCredentials):
            resolved = credentials.resolved()
            if credentials.secret_id and resolved is None:
                raise ValueError(
                    "credentials secret_id was provided without inline payload"
                )
            values["credentials"] = resolved
        return values


class DatabaseConnectorJobRequest(BaseConnectorJobRequest):
    """Request payload when launching a database ingestion job."""

    params: DatabaseConnectorParams | None = None

    @model_validator(mode="before")
    def _normalise_params(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        return values


class ApiConnectorJobRequest(BaseConnectorJobRequest):
    """Request payload when launching a REST/API ingestion job."""

    params: ApiConnectorParams | None = None

    @model_validator(mode="before")
    def _normalise_params(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        return values


class TranscriptionConnectorJobRequest(BaseConnectorJobRequest):
    """Request payload when launching a transcription ingestion job."""

    params: TranscriptionConnectorParams | None = None

    @model_validator(mode="before")
    def _normalise_params(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        return values


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
    params: (
        DatabaseSourceParams
        | ApiSourceParams
        | TranscriptionSourceParams
        | Dict[str, Any]
        | None
    ) = None
    connector_type: str | None = None
    connector_definition_id: UUID | None = None
    connector_metadata: Dict[str, Any] | None = None
    credentials: ConnectorCredentials | Dict[str, Any] | str | None = None
    sync_state: dict | None = None
    version: int | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def _normalise_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        credentials = values.get("credentials")
        if isinstance(credentials, ConnectorCredentials):
            resolved = credentials.resolved()
            if credentials.secret_id and resolved is None:
                raise ValueError(
                    "credentials secret_id was provided without inline payload"
                )
            values["credentials"] = resolved
        return values

    @model_validator(mode="after")
    def _validate_params(self) -> "SourceCreate":
        params_payload = self.params or {}
        if self.type == SourceType.DATABASE:
            if not params_payload:
                raise ValueError("database source requires params")
            DatabaseConnectorParams(**params_payload)
            if self.connector_type is None:
                object.__setattr__(self, "connector_type", "sql")
        elif self.type == SourceType.API:
            if not params_payload:
                raise ValueError("api source requires params")
            ApiConnectorParams(**params_payload)
            if self.connector_type is None:
                object.__setattr__(self, "connector_type", "rest")
        elif self.type in {SourceType.AUDIO_TRANSCRIPT, SourceType.VIDEO_TRANSCRIPT}:
            if not params_payload:
                raise ValueError("transcription source requires params")
            TranscriptionConnectorParams(**params_payload)
            if self.connector_type is None:
                object.__setattr__(self, "connector_type", "transcription")
        return self


class SourceUpdate(BaseModel):
    """Model used to update an existing source record."""

    path: str | None = None
    url: HttpUrl | None = None
    label: str | None = None
    location: str | None = None
    active: bool | None = None
    params: (
        DatabaseSourceParams
        | ApiSourceParams
        | TranscriptionSourceParams
        | Dict[str, Any]
        | None
    ) = None
    connector_type: str | None = None
    connector_definition_id: UUID | None = None
    connector_metadata: Dict[str, Any] | None = None
    credentials: ConnectorCredentials | Dict[str, Any] | str | None = None
    sync_state: dict | None = None
    version: int | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def _normalise_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        credentials = values.get("credentials")
        if isinstance(credentials, ConnectorCredentials):
            resolved = credentials.resolved()
            if credentials.secret_id and resolved is None:
                raise ValueError(
                    "credentials secret_id was provided without inline payload"
                )
            values["credentials"] = resolved
        return values


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
    params: (
        DatabaseSourceParams
        | ApiSourceParams
        | TranscriptionSourceParams
        | Dict[str, Any]
        | None
    ) = None
    connector_type: str | None = None
    connector_definition_id: UUID | None = None
    connector_metadata: Dict[str, Any] | None = None
    credentials: Any | None = None
    sync_state: dict | None = None
    version: int = 1
    created_at: datetime


class ConnectorDefinitionBase(BaseModel):
    """Shared fields for connector definitions."""

    name: str
    description: str | None = None
    type: SourceType
    params: (
        DatabaseConnectorParams
        | ApiConnectorParams
        | TranscriptionConnectorParams
        | Dict[str, Any]
        | None
    ) = None
    credentials: ConnectorCredentials | Dict[str, Any] | str | None = None
    metadata: Dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def _normalise_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        credentials = values.get("credentials")
        if isinstance(credentials, ConnectorCredentials):
            resolved = credentials.resolved()
            if credentials.secret_id and resolved is None:
                raise ValueError(
                    "credentials secret_id was provided without inline payload"
                )
            values["credentials"] = resolved
        return values

    @model_validator(mode="after")
    def _validate_params(self) -> "ConnectorDefinitionBase":
        params_payload = self.params or {}
        if self.type == SourceType.DATABASE and params_payload:
            DatabaseConnectorParams(**params_payload)
        elif self.type == SourceType.API and params_payload:
            ApiConnectorParams(**params_payload)
        elif (
            self.type in {SourceType.AUDIO_TRANSCRIPT, SourceType.VIDEO_TRANSCRIPT}
            and params_payload
        ):
            TranscriptionConnectorParams(**params_payload)
        return self


class ConnectorDefinitionCreate(ConnectorDefinitionBase):
    """Payload used to create a connector definition."""

    @model_validator(mode="after")
    def _require_params(self) -> "ConnectorDefinitionCreate":
        if self.type == SourceType.DATABASE and not self.params:
            raise ValueError("database connector definition requires params")
        if self.type == SourceType.API and not self.params:
            raise ValueError("api connector definition requires params")
        if (
            self.type in {SourceType.AUDIO_TRANSCRIPT, SourceType.VIDEO_TRANSCRIPT}
            and not self.params
        ):
            raise ValueError("transcription connector definition requires params")
        return self


class ConnectorDefinitionUpdate(BaseModel):
    """Payload used to update a connector definition."""

    name: str | None = None
    description: str | None = None
    params: (
        DatabaseConnectorParams
        | ApiConnectorParams
        | TranscriptionConnectorParams
        | Dict[str, Any]
        | None
    ) = None
    credentials: ConnectorCredentials | Dict[str, Any] | str | None = None
    metadata: Dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def _normalise_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        params = values.get("params")
        if isinstance(params, BaseModel):
            values["params"] = params.model_dump(exclude_none=True)
        credentials = values.get("credentials")
        if isinstance(credentials, ConnectorCredentials):
            resolved = credentials.resolved()
            if credentials.secret_id and resolved is None:
                raise ValueError(
                    "credentials secret_id was provided without inline payload"
                )
            values["credentials"] = resolved
        return values


class ConnectorDefinition(ConnectorDefinitionBase):
    """Representation of a stored connector definition."""

    id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    has_credentials: bool = False

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

