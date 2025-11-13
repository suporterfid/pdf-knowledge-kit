from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ..ingestion.service import ensure_schema

router = APIRouter(prefix="/api", tags=["feedback"])

logger = logging.getLogger(__name__)

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn(*, tenant_id: str) -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        conn = psycopg.connect(_DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SET app.tenant_id = %s", (tenant_id,))
        return conn
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _resolve_request_tenant(request: Request) -> str:
    tenant = getattr(request.state, "tenant_id", None)
    if not tenant:
        tenant = request.headers.get("X-Debug-Tenant")
    if not tenant:
        tenant = os.getenv("TENANT_ID")
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant identifier is required")
    return str(tenant)


class FeedbackIn(BaseModel):
    helpful: bool
    question: str | None = None
    answer: str | None = None
    sessionId: str | None = None
    sources: Any | None = None


class FeedbackCreated(BaseModel):
    id: str


@router.post("/feedback", response_model=FeedbackCreated)
def submit_feedback(payload: FeedbackIn, request: Request) -> FeedbackCreated:
    """Persist a feedback entry for quality monitoring."""
    fb_id = uuid.uuid4()
    tenant_id = _resolve_request_tenant(request)
    with _get_conn(tenant_id=tenant_id) as conn:
        # Ensure schema/migrations are applied (creates feedbacks table if missing)
        try:
            ensure_schema(conn)
        except Exception as exc:
            logger.warning("Failed to ensure feedback schema: %s", exc)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedbacks (
                    id, tenant_id, helpful, question, answer, session_id, sources, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                """,
                (
                    fb_id,
                    tenant_id,
                    payload.helpful,
                    payload.question,
                    payload.answer,
                    payload.sessionId,
                    Jsonb(payload.sources) if payload.sources is not None else None,
                ),
            )
        conn.commit()
    return FeedbackCreated(id=str(fb_id))
