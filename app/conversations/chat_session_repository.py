"""Repository for chat session persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from . import chat_session_schemas as schemas


class ChatSessionRepository:
    """Manages chat session and message persistence in the database."""

    def __init__(self, conn: psycopg.Connection, *, tenant_id: UUID) -> None:
        self._conn = conn
        self._tenant_id = tenant_id

    def create_session(
        self,
        session_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.ChatSessionDetail:
        """Create a new chat session."""
        title = title or f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        metadata = metadata or {}
        now = datetime.now(timezone.utc)

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, tenant_id, title, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, title, created_at, updated_at, metadata
                """,
                (session_id, str(self._tenant_id), title, metadata, now, now),
            )
            row = cur.fetchone()

        if not row:
            raise RuntimeError(f"Failed to create chat session {session_id}")

        return schemas.ChatSessionDetail(
            id=row[0],
            title=row[1],
            created_at=row[2],
            updated_at=row[3],
            messages=[],
            metadata=row[4] or {},
        )

    def get_session(self, session_id: str) -> schemas.ChatSessionDetail | None:
        """Retrieve a chat session with all its messages."""
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, created_at, updated_at, metadata
                FROM chat_sessions
                WHERE id = %s AND tenant_id = %s
                """,
                (session_id, str(self._tenant_id)),
            )
            session_row = cur.fetchone()

        if not session_row:
            return None

        # Fetch messages
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, role, content, sources, metadata, created_at
                FROM chat_session_messages
                WHERE session_id = %s AND tenant_id = %s
                ORDER BY created_at ASC
                """,
                (session_id, str(self._tenant_id)),
            )
            message_rows = cur.fetchall()

        messages = [
            schemas.ChatMessage(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["created_at"],
                sources=msg["sources"] or [],
                metadata=msg["metadata"] or {},
            )
            for msg in message_rows
        ]

        return schemas.ChatSessionDetail(
            id=session_row["id"],
            title=session_row["title"],
            created_at=session_row["created_at"],
            updated_at=session_row["updated_at"],
            messages=messages,
            metadata=session_row["metadata"] or {},
        )

    def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[schemas.ChatSessionSummary], int]:
        """List all chat sessions for the tenant."""
        # Get total count
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM chat_sessions WHERE tenant_id = %s",
                (str(self._tenant_id),),
            )
            total = cur.fetchone()[0]

        # Get paginated sessions
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM chat_sessions
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (str(self._tenant_id), limit, offset),
            )
            session_rows = cur.fetchall()

        sessions = []
        for row in session_rows:
            # Get message count and last message preview
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) as count, MAX(content) as last_message
                    FROM chat_session_messages
                    WHERE session_id = %s AND tenant_id = %s
                    """,
                    (row["id"], str(self._tenant_id)),
                )
                msg_row = cur.fetchone()
                message_count = msg_row[0] if msg_row else 0
                last_message = msg_row[1] if msg_row else None

            preview = None
            if last_message:
                preview = last_message[:100] + "..." if len(last_message) > 100 else last_message

            sessions.append(
                schemas.ChatSessionSummary(
                    id=row["id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=message_count,
                    last_message_preview=preview,
                )
            )

        return sessions, total

    def update_session(
        self, session_id: str, title: str | None = None
    ) -> schemas.ChatSessionDetail | None:
        """Update a chat session."""
        if title is None:
            return self.get_session(session_id)

        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET title = %s, updated_at = %s
                WHERE id = %s AND tenant_id = %s
                """,
                (title, datetime.now(timezone.utc), session_id, str(self._tenant_id)),
            )

        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages."""
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE id = %s AND tenant_id = %s",
                (session_id, str(self._tenant_id)),
            )
            return cur.rowcount > 0

    def add_message(
        self,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.ChatMessage:
        """Add a message to a chat session."""
        sources = sources or []
        metadata = metadata or {}
        now = datetime.now(timezone.utc)

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_session_messages
                (id, tenant_id, session_id, role, content, sources, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, role, content, sources, metadata, created_at
                """,
                (
                    message_id,
                    str(self._tenant_id),
                    session_id,
                    role,
                    content,
                    sources,
                    metadata,
                    now,
                ),
            )
            row = cur.fetchone()

        if not row:
            raise RuntimeError(f"Failed to add message to session {session_id}")

        return schemas.ChatMessage(
            id=row[0],
            role=row[1],
            content=row[2],
            timestamp=row[5],
            sources=row[3] or [],
            metadata=row[4] or {},
        )

    def clear_session_messages(self, session_id: str) -> bool:
        """Delete all messages from a chat session."""
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_session_messages WHERE session_id = %s AND tenant_id = %s",
                (session_id, str(self._tenant_id)),
            )
            return cur.rowcount > 0
