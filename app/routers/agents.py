"""Agent management API router."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from ..agents import schemas
from ..agents.service import (
    AgentNotFoundError,
    AgentService,
    PostgresAgentRepository,
)
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
    repo = PostgresAgentRepository(conn)
    service = AgentService(repo)
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
def list_providers(role: str = Depends(require_role("viewer"))) -> dict[str, str | None]:
    with _service_context() as svc:
        return svc.list_supported_providers()


@router.post("", response_model=schemas.AgentDetail, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: schemas.AgentCreate,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentDetail:
    with _service_context() as svc:
        return svc.create_agent(payload)


@router.get("/{agent_id}", response_model=schemas.AgentDetail)
def get_agent(agent_id: int, role: str = Depends(require_role("viewer"))) -> schemas.AgentDetail:
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
def delete_agent(agent_id: int, role: str = Depends(require_role("operator"))) -> schemas.Message:
    with _service_context() as svc:
        svc.delete_agent(agent_id)
    return schemas.Message(message="deleted")


@router.get("/{agent_id}/versions", response_model=schemas.AgentVersionList)
def list_versions(agent_id: int, role: str = Depends(require_role("viewer"))) -> schemas.AgentVersionList:
    with _service_context() as svc:
        versions = svc.list_versions(agent_id)
    return schemas.AgentVersionList(items=versions, total=len(versions))


@router.post("/{agent_id}/versions", response_model=schemas.AgentVersion, status_code=status.HTTP_201_CREATED)
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


@router.post("/{agent_id}/deploy", response_model=schemas.AgentDeployResponse)
def deploy_agent(
    agent_id: int,
    payload: schemas.AgentDeployRequest,
    role: str = Depends(require_role("operator")),
) -> schemas.AgentDeployResponse:
    with _service_context() as svc:
        return svc.deploy_agent(agent_id, payload)
