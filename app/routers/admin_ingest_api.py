"""Admin ingestion API endpoints.

This router exposes endpoints for operators to start ingestion jobs, inspect
their progress, (re)index sources and read job logs. Access is controlled via
JWT bearer tokens emitidos pelo módulo de segurança (`app.security`).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.db import apply_tenant_settings
from ..core.tenant_context import get_current_tenant_id
from ..ingestion import service, storage
from ..ingestion.models import (
    ApiConnectorJobRequest,
    ConnectorDefinition,
    ConnectorDefinitionCreate,
    ConnectorDefinitionUpdate,
    DatabaseConnectorJobRequest,
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
    TranscriptionConnectorJobRequest,
    UrlIngestRequest,
    UrlsIngestRequest,
)
from ..security.auth import require_role

router = APIRouter(prefix="/api/admin/ingest", tags=["admin-ingest"])


OperatorRole = Annotated[str, Depends(require_role("operator"))]
ViewerRole = Annotated[str, Depends(require_role("viewer"))]
OptionalSourceType = Annotated[SourceType | None, Query()]
OptionalJobStatus = Annotated[JobStatus | None, Query()]
OptionalLimit = Annotated[int | None, Query(ge=1)]
OffsetParam = Annotated[int, Query(ge=0)]
ActiveParam = Annotated[bool | None, Query()]
LogLimit = Annotated[int, Query(ge=1)]

_DATABASE_URL = os.getenv("DATABASE_URL")


def _require_tenant_id() -> UUID:
    tenant = get_current_tenant_id()
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant context missing")
    try:
        return UUID(str(tenant))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid tenant id") from exc


def _get_conn() -> psycopg.Connection:
    """Return a new database connection or raise HTTP 500."""
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        conn = psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    tenant_id = _require_tenant_id()
    try:
        apply_tenant_settings(conn, tenant_id)
    except Exception as exc:  # pragma: no cover - defensive
        conn.close()
        raise HTTPException(
            status_code=500, detail="Failed to configure tenant"
        ) from exc
    return conn


def _fetch_source(conn: psycopg.Connection, tenant_id: UUID, source_id: UUID) -> Source:
    for src in storage.list_sources(conn, tenant_id=tenant_id, active=None):
        if src.id == source_id:
            return src
    raise HTTPException(status_code=404, detail="Source not found")


def _ensure_connector_definition(
    conn: psycopg.Connection,
    tenant_id: UUID,
    definition_id: UUID,
    expected_type: SourceType | set[SourceType],
) -> ConnectorDefinition:
    definition = storage.get_connector_definition(
        conn,
        definition_id,
        tenant_id=tenant_id,
        include_credentials=True,
    )
    if not definition:
        raise HTTPException(status_code=404, detail="Connector definition not found")
    allowed_types = (
        {expected_type} if isinstance(expected_type, SourceType) else set(expected_type)
    )
    if definition.type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Connector definition type mismatch: "
                f"expected {[t.value for t in sorted(allowed_types, key=lambda t: t.value)]} "
                f"got {definition.type.value}"
            ),
        )
    return definition


def _resolve_credentials(
    provided: object | None,
    fallback: object | None,
    *,
    required: bool,
) -> object | None:
    credentials = provided if provided is not None else fallback
    if isinstance(credentials, dict) and set(credentials.keys()) == {"secret_id"}:
        raise HTTPException(
            status_code=400,
            detail=(
                "Credentials references must be resolved and stored before starting a job"
            ),
        )
    if required and credentials is None:
        raise HTTPException(
            status_code=400, detail="Credentials are required for this connector"
        )
    return credentials


def _ensure_params_for_type(
    source_type: SourceType, params: Mapping[str, Any] | BaseModel | None
) -> dict[str, Any]:
    if params is None:
        raise HTTPException(
            status_code=400,
            detail=f"{source_type.value} connector requires configuration parameters",
        )
    if isinstance(params, BaseModel):
        payload = params.model_dump()
    elif isinstance(params, Mapping):
        payload = dict(params)
    else:
        raise HTTPException(
            status_code=400,
            detail="Connector parameters must be a mapping or Pydantic model",
        )
    if source_type == SourceType.DATABASE and not payload.get("queries"):
        raise HTTPException(
            status_code=400,
            detail="Database connector requires at least one query",
        )
    if source_type == SourceType.API and not (
        payload.get("endpoint") or payload.get("base_url")
    ):
        raise HTTPException(
            status_code=400,
            detail="API connector requires an endpoint or base_url",
        )
    if source_type in {
        SourceType.AUDIO_TRANSCRIPT,
        SourceType.VIDEO_TRANSCRIPT,
    } and not payload.get("provider"):
        raise HTTPException(
            status_code=400,
            detail="Transcription connector requires a provider",
        )
    return payload


def _serialise_params(params: object | None) -> dict[str, Any] | None:
    if params is None:
        return None
    if isinstance(params, BaseModel):
        return params.model_dump()
    if isinstance(params, Mapping):
        return dict(params)
    raise HTTPException(
        status_code=400,
        detail="Connector parameters must be a mapping or Pydantic model",
    )


def _upsert_source_for_connector(
    conn: psycopg.Connection,
    *,
    tenant_id: UUID,
    source_id: UUID | None,
    source_type: SourceType,
    params: dict[str, Any],
    connector_type: str,
    connector_definition_id: UUID | None,
    connector_metadata: dict[str, Any] | None,
    credentials: object | None,
    label: str | None,
    location: str | None,
    sync_state: dict[str, Any] | None,
) -> UUID:
    if source_id:
        existing = storage.get_source(conn, source_id, tenant_id=tenant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")
        if existing.type != source_type:
            raise HTTPException(status_code=400, detail="Source type mismatch")
        storage.update_source(
            conn,
            source_id,
            tenant_id=tenant_id,
            label=label,
            location=location,
            params=params,
            connector_type=connector_type,
            connector_definition_id=connector_definition_id,
            connector_metadata=connector_metadata,
            credentials=credentials,
            sync_state=sync_state,
        )
        return source_id

    return storage.get_or_create_source(
        conn,
        tenant_id=tenant_id,
        type=source_type,
        label=label,
        location=location,
        params=params,
        connector_type=connector_type,
        connector_definition_id=connector_definition_id,
        connector_metadata=connector_metadata,
        credentials=credentials,
        sync_state=sync_state,
    )


@router.post("/local", response_model=JobCreated)
def start_local_job(
    req: LocalIngestRequest,
    role: OperatorRole,
) -> JobCreated:
    tenant_id = _require_tenant_id()
    job_id = service.ingest_local(
        Path(req.path),
        tenant_id=tenant_id,
        use_ocr=req.use_ocr,
        ocr_lang=req.ocr_lang,
    )
    return JobCreated(job_id=job_id)


@router.post("/reindex_all", response_model=ListResponse[JobCreated])
def reindex_all_sources(
    role: OperatorRole,
) -> ListResponse[JobCreated]:
    """Reindex all active sources, returning the created job IDs."""
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        sources = list(storage.list_sources(conn, tenant_id=tenant_id, active=True))
    job_ids: list[JobCreated] = []
    for src in sources:
        job_id = service.reindex_source(src.id, tenant_id=tenant_id)
        if job_id:
            job_ids.append(JobCreated(job_id=job_id))
    return ListResponse[JobCreated](items=job_ids, total=len(job_ids))


@router.post("/url", response_model=JobCreated)
def start_url_job(
    req: UrlIngestRequest,
    role: OperatorRole,
) -> JobCreated:
    tenant_id = _require_tenant_id()
    job_id = service.ingest_url(str(req.url), tenant_id=tenant_id)
    return JobCreated(job_id=job_id)


@router.post("/urls", response_model=JobCreated)
def start_urls_job(
    req: UrlsIngestRequest,
    role: OperatorRole,
) -> JobCreated:
    tenant_id = _require_tenant_id()
    job_id = service.ingest_urls([str(u) for u in req.urls], tenant_id=tenant_id)
    return JobCreated(job_id=job_id)


@router.post("/database", response_model=JobCreated)
def start_database_connector_job(
    req: DatabaseConnectorJobRequest,
    role: OperatorRole,
) -> JobCreated:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        definition = (
            _ensure_connector_definition(
                conn, tenant_id, req.connector_definition_id, SourceType.DATABASE
            )
            if req.connector_definition_id
            else None
        )
        params_source = req.params or (definition.params if definition else None)
        params = _ensure_params_for_type(SourceType.DATABASE, params_source)
        credentials = _resolve_credentials(
            req.credentials,
            definition.credentials if definition else None,
            required=True,
        )
        metadata = req.connector_metadata
        if metadata is None and definition and definition.metadata is not None:
            metadata = dict(definition.metadata)
        label = req.label or (definition.name if definition else None)
        location = req.location
        if location is None and metadata and isinstance(metadata, dict):
            location = metadata.get("location")
        source_id = _upsert_source_for_connector(
            conn,
            tenant_id=tenant_id,
            source_id=req.source_id,
            source_type=SourceType.DATABASE,
            params=params,
            connector_type="sql",
            connector_definition_id=req.connector_definition_id,
            connector_metadata=metadata,
            credentials=credentials,
            label=label,
            location=location,
            sync_state=req.sync_state,
        )
    job_id = service.ingest_source(source_id, tenant_id=tenant_id)
    return JobCreated(job_id=job_id)


@router.post("/api", response_model=JobCreated)
def start_api_connector_job(
    req: ApiConnectorJobRequest,
    role: OperatorRole,
) -> JobCreated:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        definition = (
            _ensure_connector_definition(
                conn, tenant_id, req.connector_definition_id, SourceType.API
            )
            if req.connector_definition_id
            else None
        )
        params_source = req.params or (definition.params if definition else None)
        params = _ensure_params_for_type(SourceType.API, params_source)
        credentials = _resolve_credentials(
            req.credentials,
            definition.credentials if definition else None,
            required=False,
        )
        metadata = req.connector_metadata
        if metadata is None and definition and definition.metadata is not None:
            metadata = dict(definition.metadata)
        label = req.label or (definition.name if definition else None)
        location = req.location
        if location is None and metadata and isinstance(metadata, dict):
            location = metadata.get("location")
        source_id = _upsert_source_for_connector(
            conn,
            tenant_id=tenant_id,
            source_id=req.source_id,
            source_type=SourceType.API,
            params=params,
            connector_type="rest",
            connector_definition_id=req.connector_definition_id,
            connector_metadata=metadata,
            credentials=credentials,
            label=label,
            location=location,
            sync_state=req.sync_state,
        )
    job_id = service.ingest_source(source_id, tenant_id=tenant_id)
    return JobCreated(job_id=job_id)


@router.post("/transcription", response_model=JobCreated)
def start_transcription_connector_job(
    req: TranscriptionConnectorJobRequest,
    role: OperatorRole,
) -> JobCreated:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        if req.connector_definition_id:
            definition = _ensure_connector_definition(
                conn,
                tenant_id,
                req.connector_definition_id,
                {SourceType.AUDIO_TRANSCRIPT, SourceType.VIDEO_TRANSCRIPT},
            )
            expected_type = definition.type
        else:
            definition = None
            expected_type = SourceType.AUDIO_TRANSCRIPT
            if (
                req.connector_metadata
                and req.connector_metadata.get("media_type") == "video"
            ):
                expected_type = SourceType.VIDEO_TRANSCRIPT
        params_source = req.params or (definition.params if definition else None)
        params = _ensure_params_for_type(expected_type, params_source)
        credentials = _resolve_credentials(
            req.credentials,
            definition.credentials if definition else None,
            required=False,
        )
        metadata = req.connector_metadata
        if metadata is None and definition and definition.metadata is not None:
            metadata = dict(definition.metadata)
        label = req.label or (definition.name if definition else None)
        location = req.location
        if location is None and metadata and isinstance(metadata, dict):
            location = metadata.get("location")
        source_id = _upsert_source_for_connector(
            conn,
            tenant_id=tenant_id,
            source_id=req.source_id,
            source_type=expected_type,
            params=params,
            connector_type="transcription",
            connector_definition_id=req.connector_definition_id,
            connector_metadata=metadata,
            credentials=credentials,
            label=label,
            location=location,
            sync_state=req.sync_state,
        )
    job_id = service.ingest_source(source_id, tenant_id=tenant_id)
    return JobCreated(job_id=job_id)


@router.get("/connector_definitions", response_model=ListResponse[ConnectorDefinition])
def list_connector_definitions(
    role: ViewerRole,
    type: OptionalSourceType = None,
    limit: OptionalLimit = None,
    offset: OffsetParam = 0,
) -> ListResponse[ConnectorDefinition]:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        all_defs = list(
            storage.list_connector_definitions(
                conn,
                tenant_id=tenant_id,
                type=type,
                include_credentials=False,
            )
        )
    total = len(all_defs)
    items = all_defs[offset:]
    if limit is not None:
        items = items[:limit]
    return ListResponse[ConnectorDefinition](items=items, total=total)


@router.post("/connector_definitions", response_model=ConnectorDefinition)
def create_connector_definition_endpoint(
    req: ConnectorDefinitionCreate,
    role: OperatorRole,
) -> ConnectorDefinition:
    tenant_id = _require_tenant_id()
    if req.tenant_id and req.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    with _get_conn() as conn:
        definition_id = storage.create_connector_definition(
            conn,
            tenant_id=tenant_id,
            name=req.name,
            type=req.type,
            description=req.description,
            params=_serialise_params(req.params),
            credentials=req.credentials,
            metadata=req.metadata,
        )
        created = storage.get_connector_definition(
            conn,
            definition_id,
            tenant_id=tenant_id,
            include_credentials=False,
        )
    if not created:
        raise HTTPException(
            status_code=500, detail="Failed to create connector definition"
        )
    return created


@router.get(
    "/connector_definitions/{definition_id}", response_model=ConnectorDefinition
)
def get_connector_definition_endpoint(
    definition_id: UUID,
    role: ViewerRole,
) -> ConnectorDefinition:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        definition = storage.get_connector_definition(
            conn,
            definition_id,
            tenant_id=tenant_id,
            include_credentials=False,
        )
    if not definition:
        raise HTTPException(status_code=404, detail="Connector definition not found")
    return definition


@router.put(
    "/connector_definitions/{definition_id}", response_model=ConnectorDefinition
)
def update_connector_definition_endpoint(
    definition_id: UUID,
    req: ConnectorDefinitionUpdate,
    role: OperatorRole,
) -> ConnectorDefinition:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        existing = storage.get_connector_definition(
            conn,
            definition_id,
            tenant_id=tenant_id,
            include_credentials=True,
        )
        if not existing:
            raise HTTPException(
                status_code=404, detail="Connector definition not found"
            )
        credentials_param: object
        if "credentials" in req.model_fields_set:
            credentials_param = req.credentials
        else:
            credentials_param = storage._MISSING
        storage.update_connector_definition(
            conn,
            definition_id,
            tenant_id=tenant_id,
            name=req.name,
            description=req.description,
            params=_serialise_params(req.params),
            credentials=credentials_param,
            metadata=req.metadata,
        )
        updated = storage.get_connector_definition(
            conn,
            definition_id,
            tenant_id=tenant_id,
            include_credentials=False,
        )
    if not updated:
        raise HTTPException(
            status_code=500, detail="Failed to update connector definition"
        )
    return updated


@router.delete(
    "/connector_definitions/{definition_id}", response_model=ConnectorDefinition
)
def delete_connector_definition_endpoint(
    definition_id: UUID,
    role: OperatorRole,
) -> ConnectorDefinition:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        definition = storage.get_connector_definition(
            conn,
            definition_id,
            tenant_id=tenant_id,
            include_credentials=False,
        )
        if not definition:
            raise HTTPException(
                status_code=404, detail="Connector definition not found"
            )
        storage.delete_connector_definition(conn, definition_id, tenant_id=tenant_id)
    return definition


@router.get("/jobs", response_model=ListResponse[Job])
def list_jobs(
    role: ViewerRole,
    status: OptionalJobStatus = None,
    limit: OptionalLimit = None,
    offset: OffsetParam = 0,
) -> ListResponse[Job]:
    tenant_id = _require_tenant_id()
    jobs = service.list_jobs(tenant_id=tenant_id)
    if status is not None:
        jobs = [j for j in jobs if j.status == status]
    total = len(jobs)
    if offset:
        jobs = jobs[offset:]
    if limit is not None:
        jobs = jobs[:limit]
    return ListResponse[Job](items=jobs, total=total)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: UUID, role: ViewerRole) -> Job:
    tenant_id = _require_tenant_id()
    job = service.get_job(job_id, tenant_id=tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: UUID, role: OperatorRole) -> Job:
    tenant_id = _require_tenant_id()
    service.cancel_job(job_id, tenant_id=tenant_id)
    job = service.get_job(job_id, tenant_id=tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/rerun", response_model=JobCreated)
def rerun_job_endpoint(job_id: UUID, role: OperatorRole) -> JobCreated:
    tenant_id = _require_tenant_id()
    new_job_id = service.rerun_job(job_id, tenant_id=tenant_id)
    if not new_job_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobCreated(job_id=new_job_id)


@router.get("/jobs/{job_id}/logs", response_model=JobLogSlice)
def get_job_logs(
    job_id: UUID,
    role: ViewerRole,
    offset: OffsetParam = 0,
    limit: LogLimit = 16_384,
) -> JobLogSlice:
    """Return a slice of the job log starting at ``offset``."""
    tenant_id = _require_tenant_id()
    return service.read_job_log(job_id, tenant_id=tenant_id, offset=offset, limit=limit)


@router.get("/sources", response_model=ListResponse[Source])
def list_sources(
    role: ViewerRole,
    active: ActiveParam = True,
    type: OptionalSourceType = None,
    limit: OptionalLimit = None,
    offset: OffsetParam = 0,
) -> ListResponse[Source]:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        all_items = list(
            storage.list_sources(conn, tenant_id=tenant_id, active=active, type=type)
        )
        total = len(all_items)
        items = all_items[offset:]
        if limit is not None:
            items = items[:limit]
        return ListResponse[Source](items=items, total=total)


@router.post("/sources", response_model=Source)
def create_source(req: SourceCreate, role: OperatorRole) -> Source:
    tenant_id = _require_tenant_id()
    if req.tenant_id and req.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    with _get_conn() as conn:
        source_id = storage.get_or_create_source(
            conn,
            tenant_id=tenant_id,
            type=req.type,
            path=req.path,
            url=str(req.url) if req.url else None,
            label=req.label,
            location=req.location,
            active=req.active,
            params=_serialise_params(req.params),
            connector_type=req.connector_type,
            connector_definition_id=req.connector_definition_id,
            connector_metadata=req.connector_metadata,
            credentials=req.credentials,
            sync_state=req.sync_state,
            version=req.version,
        )
        return _fetch_source(conn, tenant_id, source_id)


@router.put("/sources/{source_id}", response_model=Source)
def update_source(
    source_id: UUID,
    req: SourceUpdate,
    role: OperatorRole,
) -> Source:
    tenant_id = _require_tenant_id()
    if req.tenant_id and req.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    with _get_conn() as conn:
        storage.update_source(
            conn,
            source_id,
            tenant_id=tenant_id,
            path=req.path,
            url=str(req.url) if req.url else None,
            label=req.label,
            location=req.location,
            active=req.active,
            params=_serialise_params(req.params),
            connector_type=req.connector_type,
            connector_definition_id=req.connector_definition_id,
            connector_metadata=req.connector_metadata,
            credentials=req.credentials,
            sync_state=req.sync_state,
            version=req.version,
        )
        return _fetch_source(conn, tenant_id, source_id)


@router.delete("/sources/{source_id}", response_model=Source)
def delete_source(source_id: UUID, role: OperatorRole) -> Source:
    tenant_id = _require_tenant_id()
    with _get_conn() as conn:
        src = _fetch_source(conn, tenant_id, source_id)
        storage.soft_delete_source(conn, source_id, tenant_id=tenant_id)
        src.active = False
        return src


@router.post("/sources/{source_id}/reindex", response_model=JobCreated)
def reindex_source_endpoint(source_id: UUID, role: OperatorRole) -> JobCreated:
    tenant_id = _require_tenant_id()
    job_id = service.reindex_source(source_id, tenant_id=tenant_id)
    if not job_id:
        raise HTTPException(status_code=404, detail="Source not found")
    return JobCreated(job_id=job_id)
