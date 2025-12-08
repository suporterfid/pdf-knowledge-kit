"""Chat session management API routes."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..conversations import chat_session_schemas as schemas
from ..conversations.chat_session_repository import ChatSessionRepository
from ..conversations.chat_session_service import ChatSessionService
from ..core.db import get_required_tenant_id

router = APIRouter(tags=["chat-sessions"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@contextmanager
def _service_context() -> Iterator[ChatSessionService]:
    conn = _get_conn()
    try:
        tenant_id = get_required_tenant_id()
    except RuntimeError as exc:
        conn.close()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        conn.close()
        raise HTTPException(
            status_code=500, detail="Failed to resolve tenant"
        ) from exc

    repo = ChatSessionRepository(conn, tenant_id=tenant_id)
    service = ChatSessionService(repo)
    try:
        yield service
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/api/chat-sessions", response_model=schemas.ChatSessionDetail)
def create_chat_session(
    payload: schemas.ChatSessionCreate | None = None,
) -> schemas.ChatSessionDetail:
    """Create a new chat session."""
    with _service_context() as service:
        title = payload.title if payload else None
        return service.create_session(title)


@router.get("/api/chat-sessions", response_model=schemas.ChatSessionList)
def list_chat_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> schemas.ChatSessionList:
    """List all chat sessions for the current tenant."""
    with _service_context() as service:
        items, total = service.list_sessions(limit, offset)
        return schemas.ChatSessionList(items=items, total=total)


@router.get("/api/chat-sessions/{session_id}", response_model=schemas.ChatSessionDetail)
def get_chat_session(session_id: str) -> schemas.ChatSessionDetail:
    """Retrieve a chat session with all its messages."""
    with _service_context() as service:
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session


@router.patch("/api/chat-sessions/{session_id}", response_model=schemas.ChatSessionDetail)
def update_chat_session(
    session_id: str,
    payload: schemas.ChatSessionUpdate,
) -> schemas.ChatSessionDetail:
    """Update a chat session."""
    with _service_context() as service:
        session = service.update_session(session_id, payload.title)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session


@router.delete("/api/chat-sessions/{session_id}")
def delete_chat_session(session_id: str) -> dict[str, str]:
    """Delete a chat session."""
    with _service_context() as service:
        if not service.delete_session(session_id):
            raise HTTPException(status_code=404, detail="Chat session not found")
        return {"message": "Chat session deleted"}


@router.post(
    "/api/chat-sessions/{session_id}/messages",
    response_model=schemas.AddMessageResponse,
)
def add_message_to_session(
    session_id: str,
    payload: schemas.AddMessageRequest,
) -> schemas.AddMessageResponse:
    """Add a message to a chat session."""
    with _service_context() as service:
        # Verify session exists
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        return service.add_message(
            session_id,
            payload.role,
            payload.content,
            payload.sources,
            payload.metadata,
        )


@router.delete("/api/chat-sessions/{session_id}/messages")
def clear_session_messages(session_id: str) -> dict[str, str]:
    """Clear all messages from a chat session."""
    with _service_context() as service:
        if not service.clear_session_messages(session_id):
            raise HTTPException(status_code=404, detail="Chat session not found")
        return {"message": "Messages cleared"}
