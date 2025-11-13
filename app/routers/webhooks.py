"""Webhook ingestion routes for external messaging channels."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response, status

from ..agents.service import (
    AgentNotFoundError,
    AgentService,
    PostgresAgentRepository,
)
from ..channels import get_adapter
from ..conversations import schemas as convo_schemas
from ..conversations.repository import PostgresConversationRepository
from ..conversations.service import ConversationService
from ..core.db import apply_tenant_settings, get_required_tenant_id

router = APIRouter(tags=["webhooks"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@contextmanager
def _service_context(
    tenant_id: UUID,
) -> Iterator[tuple[AgentService, ConversationService]]:
    conn = _get_conn()
    try:
        apply_tenant_settings(conn, tenant_id)
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


def _resolve_tenant_id(request: Request) -> UUID:
    header = request.headers.get("x-tenant-id") or request.headers.get(
        "x-chatvolt-tenant"
    )
    candidate = header or request.query_params.get("tenant_id")
    try:
        return get_required_tenant_id(candidate)
    except RuntimeError as exc:
        status_code = 400 if candidate else 403
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/api/webhooks/{agent_slug}/{channel}")
async def ingest_webhook(agent_slug: str, channel: str, request: Request) -> Response:
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON payload: {exc}"
        ) from exc

    channel_name = channel.lower()
    try:
        adapter_cls = get_adapter(channel_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    tenant_id = _resolve_tenant_id(request)

    with _service_context(tenant_id) as (agents, conversations):
        agent = agents.get_agent_by_slug(agent_slug)
        try:
            channel_config = agents.get_channel_config(agent.id, channel_name)
            config_dict = json.loads(channel_config.model_dump_json())
        except AgentNotFoundError:
            config_dict = {}
        adapter = adapter_cls(agent_id=agent.id)
        if not adapter.verify_signature(body_bytes, request.headers, config_dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
            )
        normalized_messages = list(
            adapter.parse_incoming(payload, request.headers, config_dict)
        )
        if not normalized_messages:
            return Response(status_code=status.HTTP_202_ACCEPTED)
        processed = 0
        last_response: convo_schemas.MessageIngestResponse | None = None
        for normalized in normalized_messages:
            # Ensure normalized message carries correct agent/channel context
            normalized.agent_id = agent.id
            normalized.channel = channel_name
            normalized.tenant_id = tenant_id
            result = conversations.process_incoming_message(
                agent, normalized, config_dict
            )
            processed += 1
            last_response = result
        if last_response:
            return Response(
                content=last_response.copy(
                    update={"processed_messages": processed}
                ).model_dump_json(),
                media_type="application/json",
            )
        return Response(status_code=status.HTTP_202_ACCEPTED)
