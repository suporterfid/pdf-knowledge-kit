from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from psycopg.types.json import Jsonb
from ..ingestion.service import ensure_schema


router = APIRouter(prefix="/api", tags=["feedback"])

_DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn() -> psycopg.Connection:
    if not _DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    try:
        return psycopg.connect(_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class FeedbackIn(BaseModel):
    helpful: bool
    question: Optional[str] = None
    answer: Optional[str] = None
    sessionId: Optional[str] = None
    sources: Optional[Any] = None


class FeedbackCreated(BaseModel):
    id: str


@router.post("/feedback", response_model=FeedbackCreated)
def submit_feedback(payload: FeedbackIn) -> FeedbackCreated:
    """Persist a feedback entry for quality monitoring."""
    fb_id = uuid.uuid4()
    with _get_conn() as conn:
        # Ensure schema/migrations are applied (creates feedbacks table if missing)
        try:
            ensure_schema(conn)
        except Exception:
            pass
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedbacks (id, helpful, question, answer, session_id, sources, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                """,
                (
                    fb_id,
                    payload.helpful,
                    payload.question,
                    payload.answer,
                    payload.sessionId,
                    Jsonb(payload.sources) if payload.sources is not None else None,
                ),
            )
        conn.commit()
    return FeedbackCreated(id=str(fb_id))
