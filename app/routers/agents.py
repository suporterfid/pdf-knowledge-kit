"""Agent management API router."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from ..agents import schemas
from ..agents.service import (
    AgentNotFoundError,
    AgentService,
    PostgresAgentRepository,
)
from ..core.db import apply_tenant_settings, get_required_tenant_id
from ..security.auth import require_role

router = APIRouter(prefix="/api/agents", tags=["agents"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@contextmanager
def _service_context() -> Iterator[AgentService]:
    conn = _get_conn()
    try:
        tenant_id = get_required_tenant_id()
        apply_tenant_settings(conn, tenant_id)
    except RuntimeError as exc:
        conn.close()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        conn.close()
        raise HTTPException(
            status_code=500, detail="Failed to configure tenant"
        ) from exc
    repo = PostgresAgentRepository(conn, tenant_id=tenant_id)
    service = AgentService(repo, tenant_id=tenant_id)
    try:
        yield service
        conn.commit()
    except AgentNotFoundError as exc:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("", response_model=schemas.AgentList)
def list_agents(role: str = Depends(require_role("viewer"))) -> schemas.AgentList:
    with _service_context() as svc:
        agents = svc.list_agents()
    return schemas.AgentList(items=agents, total=len(agents))


@router.get("/providers", response_model=dict[str, str | None])
def list_providers(
    role: str = Depends(require_role("viewer")),
) -> dict[str, str | None]:
    with _service_context() as svc:
        return svc.list_supported_providers()


@router.post(
    "", response_model=schemas.AgentDetail, status_code=status.HTTP_201_CREATED
)
def create_agent(
    payload: schemas.AgentCreate,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentDetail:
    with _service_context() as svc:
        return svc.create_agent(payload)


@router.get("/{agent_id}", response_model=schemas.AgentDetail)
def get_agent(
    agent_id: int, role: str = Depends(require_role("viewer"))
) -> schemas.AgentDetail:
    with _service_context() as svc:
        return svc.get_agent(agent_id)


@router.put("/{agent_id}", response_model=schemas.AgentDetail)
def update_agent(
    agent_id: int,
    payload: schemas.AgentUpdate,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentDetail:
    with _service_context() as svc:
        return svc.update_agent(agent_id, payload)


@router.delete("/{agent_id}", response_model=schemas.Message)
def delete_agent(
    agent_id: int, role: str = Depends(require_role("operator"))
) -> schemas.Message:
    with _service_context() as svc:
        svc.delete_agent(agent_id)
    return schemas.Message(message="deleted")


@router.get("/{agent_id}/versions", response_model=schemas.AgentVersionList)
def list_versions(
    agent_id: int, role: str = Depends(require_role("viewer"))
) -> schemas.AgentVersionList:
    with _service_context() as svc:
        versions = svc.list_versions(agent_id)
    return schemas.AgentVersionList(items=versions, total=len(versions))


@router.post(
    "/{agent_id}/versions",
    response_model=schemas.AgentVersion,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    agent_id: int,
    payload: schemas.AgentVersionCreate,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentVersion:
    with _service_context() as svc:
        return svc.create_version(agent_id, payload)


@router.post("/{agent_id}/test", response_model=schemas.AgentTestResponse)
def test_agent(
    agent_id: int,
    payload: schemas.AgentTestRequest,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentTestResponse:
    with _service_context() as svc:
        return svc.run_test(agent_id, payload)


@router.get("/{agent_id}/tests", response_model=list[schemas.AgentTestRecord])
def list_tests(agent_id: int, role: str = Depends(require_role("viewer"))):
    with _service_context() as svc:
        return svc.list_tests(agent_id)


@router.get("/{agent_id}/channels", response_model=schemas.ChannelConfigList)
def list_channel_configs(
    agent_id: int, role: str = Depends(require_role("viewer"))
) -> schemas.ChannelConfigList:
    with _service_context() as svc:
        configs = svc.list_channel_configs(agent_id)
    return schemas.ChannelConfigList(items=configs, total=len(configs))


@router.get("/{agent_id}/channels/{channel}", response_model=schemas.ChannelConfig)
def get_channel_config(
    agent_id: int, channel: str, role: str = Depends(require_role("viewer"))
) -> schemas.ChannelConfig:
    with _service_context() as svc:
        return svc.get_channel_config(agent_id, channel)


@router.put("/{agent_id}/channels/{channel}", response_model=schemas.ChannelConfig)
def upsert_channel_config(
    agent_id: int,
    channel: str,
    payload: schemas.ChannelConfigUpdate,
    role: str = Depends(require_role("operator")),
) -> schemas.ChannelConfig:
    with _service_context() as svc:
        return svc.upsert_channel_config(agent_id, channel, payload)


@router.delete("/{agent_id}/channels/{channel}", response_model=schemas.Message)
def delete_channel_config(
    agent_id: int, channel: str, role: str = Depends(require_role("operator"))
) -> schemas.Message:
    with _service_context() as svc:
        svc.delete_channel_config(agent_id, channel)
    return schemas.Message(message="deleted")


@router.post("/{agent_id}/deploy", response_model=schemas.AgentDeployResponse)
def deploy_agent(
    agent_id: int,
    payload: schemas.AgentDeployRequest,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentDeployResponse:
    with _service_context() as svc:
        deployed = svc.deploy_agent(agent_id, payload)
    return schemas.AgentDeployResponse.model_validate(deployed.model_dump())
