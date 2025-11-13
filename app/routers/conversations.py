"""Conversation management API routes."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from ..agents.service import AgentNotFoundError, AgentService, PostgresAgentRepository
from ..conversations import schemas as convo_schemas
from ..conversations.repository import PostgresConversationRepository
from ..conversations.service import ConversationService
from ..core.db import apply_tenant_settings, get_required_tenant_id
from ..security.auth import require_role

router = APIRouter(tags=["conversations"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@contextmanager
def _service_context() -> Iterator[tuple[AgentService, ConversationService]]:
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
    agent_repo = PostgresAgentRepository(conn, tenant_id=tenant_id)
    convo_repo = PostgresConversationRepository(conn, tenant_id=tenant_id)
    agent_service = AgentService(agent_repo, tenant_id=tenant_id)
    convo_service = ConversationService(convo_repo, tenant_id=tenant_id)
    try:
        yield agent_service, convo_service
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


@router.get(
    "/api/agents/{agent_id}/conversations",
    response_model=convo_schemas.ConversationList,
)
def list_conversations(
    agent_id: int,
    limit: int = 20,
    role: str = Depends(require_role("viewer")),
) -> convo_schemas.ConversationList:
    with _service_context() as (_, conversations):
        return conversations.list_conversations(agent_id, limit=limit)


@router.get(
    "/api/agents/{agent_id}/conversations/dashboard",
    response_model=convo_schemas.ConversationDashboardPayload,
)
def conversation_dashboard(
    agent_id: int,
    limit: int = 10,
    role: str = Depends(require_role("viewer")),
) -> convo_schemas.ConversationDashboardPayload:
    with _service_context() as (_, conversations):
        return conversations.dashboard_snapshot(agent_id, limit=limit)


@router.get(
    "/api/conversations/{conversation_id}",
    response_model=convo_schemas.ConversationDetail,
)
def get_conversation(
    conversation_id: int,
    role: str = Depends(require_role("viewer")),
) -> convo_schemas.ConversationDetail:
    with _service_context() as (_, conversations):
        try:
            return conversations.get_conversation(conversation_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/api/conversations/{conversation_id}/follow-up",
    response_model=convo_schemas.FollowUpResponse,
)
def schedule_follow_up(
    conversation_id: int,
    payload: convo_schemas.FollowUpRequest,
    role: str = Depends(require_role("operator")),
) -> convo_schemas.FollowUpResponse:
    with _service_context() as (_, conversations):
        detail = conversations.schedule_follow_up(
            conversation_id,
            payload.follow_up_at,
            payload.note,
        )
    return convo_schemas.FollowUpResponse(**detail.model_dump())


@router.post(
    "/api/conversations/{conversation_id}/escalate",
    response_model=convo_schemas.EscalationResponse,
)
def escalate_conversation(
    conversation_id: int,
    payload: convo_schemas.EscalationRequest,
    resolve: bool = False,
    role: str = Depends(require_role("operator")),
) -> convo_schemas.EscalationResponse:
    with _service_context() as (_, conversations):
        if resolve:
            detail = conversations.resolve_escalation(conversation_id)
        else:
            detail = conversations.escalate(
                conversation_id, payload.reason, payload.escalate_to
            )
    return convo_schemas.EscalationResponse(**detail.model_dump())
