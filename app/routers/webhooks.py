"""Webhook ingestion routes for external messaging channels."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Iterator, Tuple

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response, status

from ..agents.service import (
    AgentNotFoundError,
    AgentService,
    PostgresAgentRepository,
)
from ..channels import get_adapter
from ..conversations.repository import PostgresConversationRepository
from ..conversations.service import ConversationService
from ..conversations import schemas as convo_schemas

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
def _service_context() -> Iterator[Tuple[AgentService, ConversationService]]:
    conn = _get_conn()
    agent_repo = PostgresAgentRepository(conn)
    convo_repo = PostgresConversationRepository(conn)
    agent_service = AgentService(agent_repo)
    convo_service = ConversationService(convo_repo)
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


@router.post("/api/webhooks/{agent_slug}/{channel}")
async def ingest_webhook(agent_slug: str, channel: str, request: Request) -> Response:
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    channel_name = channel.lower()
    try:
        adapter_cls = get_adapter(channel_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    with _service_context() as (agents, conversations):
        agent = agents.get_agent_by_slug(agent_slug)
        try:
            channel_config = agents.get_channel_config(agent.id, channel_name)
            config_dict = json.loads(channel_config.model_dump_json())
        except AgentNotFoundError:
            config_dict = {}
        adapter = adapter_cls(agent_id=agent.id)
        if not adapter.verify_signature(body_bytes, request.headers, config_dict):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
        normalized_messages = list(adapter.parse_incoming(payload, request.headers, config_dict))
        if not normalized_messages:
            return Response(status_code=status.HTTP_202_ACCEPTED)
        processed = 0
        last_response: convo_schemas.MessageIngestResponse | None = None
        for normalized in normalized_messages:
            # Ensure normalized message carries correct agent/channel context
            normalized.agent_id = agent.id
            normalized.channel = channel_name
            result = conversations.process_incoming_message(agent, normalized, config_dict)
            processed += 1
            last_response = result
        if last_response:
            return Response(
                content=last_response.copy(update={"processed_messages": processed}).model_dump_json(),
                media_type="application/json",
            )
        return Response(status_code=status.HTTP_202_ACCEPTED)
