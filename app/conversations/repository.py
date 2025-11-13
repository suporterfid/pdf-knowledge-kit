"""Database repository for conversations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.db import get_required_tenant_id

from . import schemas


class ConversationRepository(Protocol):
    """Abstraction for persisting conversation artefacts."""

    def get_by_external(
        self, agent_id: int, channel: str, external_conversation_id: str
    ) -> schemas.ConversationDetail | None: ...

    def create_conversation(
        self,
        agent_id: int,
        channel: str,
        external_conversation_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.ConversationDetail: ...

    def add_participant(
        self,
        conversation_id: int,
        role: str,
        external_id: str | None,
        display_name: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.ConversationParticipant: ...

    def get_participant(
        self,
        conversation_id: int,
        role: str,
        external_id: str | None,
    ) -> schemas.ConversationParticipant | None: ...

    def add_message(
        self,
        conversation_id: int,
        participant_id: int | None,
        direction: str,
        body: dict[str, Any],
        nlp: dict[str, Any],
        sent_at: datetime,
    ) -> schemas.ConversationMessage: ...

    def update_conversation_touch(
        self,
        conversation_id: int,
        *,
        last_message_at: datetime,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def list_conversations(
        self, agent_id: int, limit: int = 50
    ) -> list[schemas.ConversationSummary]: ...

    def get_conversation(
        self, conversation_id: int
    ) -> schemas.ConversationDetail | None: ...

    def set_follow_up(
        self,
        conversation_id: int,
        follow_up_at: datetime | None,
        note: str | None,
    ) -> None: ...

    def mark_escalated(
        self,
        conversation_id: int,
        *,
        is_escalated: bool,
        reason: str | None,
        escalate_to: str | None,
    ) -> None: ...

    def analytics(self, agent_id: int) -> schemas.ConversationAnalytics: ...

    def channel_analytics(
        self, agent_id: int
    ) -> list[schemas.ChannelConfigAnalytics]: ...


class PostgresConversationRepository:
    """PostgreSQL implementation of :class:`ConversationRepository`."""

    def __init__(self, conn: psycopg.Connection, tenant_id: UUID | None = None) -> None:
        self._conn = conn
        self._tenant_id = get_required_tenant_id(tenant_id)

    # Utility -----------------------------------------------------------------
    def _cursor(self):
        return self._conn.cursor(row_factory=dict_row)

    @property
    def tenant_id(self) -> UUID:
        return self._tenant_id

    # Conversation operations --------------------------------------------------
    def get_by_external(
        self, agent_id: int, channel: str, external_conversation_id: str
    ) -> schemas.ConversationDetail | None:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM conversations
                WHERE tenant_id = %s AND agent_id = %s AND channel = %s AND external_conversation_id = %s
                """,
                (self._tenant_id, agent_id, channel, external_conversation_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._hydrate_conversation(row)

    def create_conversation(
        self,
        agent_id: int,
        channel: str,
        external_conversation_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.ConversationDetail:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (tenant_id, agent_id, channel, external_conversation_id, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    self._tenant_id,
                    agent_id,
                    channel,
                    external_conversation_id,
                    Jsonb(metadata or {}),
                ),
            )
            row = cur.fetchone()
        return self._hydrate_conversation(row)

    def add_participant(
        self,
        conversation_id: int,
        role: str,
        external_id: str | None,
        display_name: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.ConversationParticipant:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_participants
                    (tenant_id, conversation_id, role, external_id, display_name, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    self._tenant_id,
                    conversation_id,
                    role,
                    external_id,
                    display_name,
                    Jsonb(metadata or {}),
                ),
            )
            row = cur.fetchone()
        return schemas.ConversationParticipant(**row)

    def get_participant(
        self,
        conversation_id: int,
        role: str,
        external_id: str | None,
    ) -> schemas.ConversationParticipant | None:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM conversation_participants
                WHERE tenant_id = %s AND conversation_id = %s AND role = %s
                  AND coalesce(external_id, '') = coalesce(%s, '')
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (self._tenant_id, conversation_id, role, external_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return schemas.ConversationParticipant(**row)

    def add_message(
        self,
        conversation_id: int,
        participant_id: int | None,
        direction: str,
        body: dict[str, Any],
        nlp: dict[str, Any],
        sent_at: datetime,
    ) -> schemas.ConversationMessage:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_messages
                    (tenant_id, conversation_id, participant_id, direction, body, nlp, sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    self._tenant_id,
                    conversation_id,
                    participant_id,
                    direction,
                    Jsonb(body),
                    Jsonb(nlp),
                    sent_at,
                ),
            )
            row = cur.fetchone()
        return schemas.ConversationMessage(**row)

    def update_conversation_touch(
        self,
        conversation_id: int,
        *,
        last_message_at: datetime,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        assignments: list[sql.Composable] = [
            sql.SQL("{} = %s").format(sql.Identifier("last_message_at"))
        ]
        values: list[Any] = [last_message_at]
        if status is not None:
            assignments.append(sql.SQL("{} = %s").format(sql.Identifier("status")))
            values.append(status)
        if metadata is not None:
            assignments.append(sql.SQL("{} = %s").format(sql.Identifier("metadata")))
            values.append(Jsonb(metadata))
        values.extend((self._tenant_id, conversation_id))
        set_clause = sql.SQL(", ").join(assignments + [sql.SQL("updated_at = now()")])
        query = sql.SQL(
            "UPDATE conversations SET {} WHERE tenant_id = %s AND id = %s"
        ).format(set_clause)
        with self._cursor() as cur:
            cur.execute(query, values)

    def list_conversations(
        self, agent_id: int, limit: int = 50
    ) -> list[schemas.ConversationSummary]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_id, channel, external_conversation_id, status, is_escalated,
                       escalation_reason, follow_up_at, follow_up_note, last_message_at, metadata
                FROM conversations
                WHERE tenant_id = %s AND agent_id = %s
                ORDER BY last_message_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (self._tenant_id, agent_id, limit),
            )
            rows = cur.fetchall()
        return [schemas.ConversationSummary(**row) for row in rows]

    def get_conversation(
        self, conversation_id: int
    ) -> schemas.ConversationDetail | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM conversations WHERE tenant_id = %s AND id = %s",
                (self._tenant_id, conversation_id),
            )
            convo = cur.fetchone()
            if not convo:
                return None
            cur.execute(
                """
                SELECT * FROM conversation_participants
                WHERE tenant_id = %s AND conversation_id = %s
                ORDER BY created_at
                """,
                (self._tenant_id, conversation_id),
            )
            participants = [
                schemas.ConversationParticipant(**row) for row in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT * FROM conversation_messages
                WHERE tenant_id = %s AND conversation_id = %s
                ORDER BY sent_at ASC
                """,
                (self._tenant_id, conversation_id),
            )
            messages = [schemas.ConversationMessage(**row) for row in cur.fetchall()]
        detail = self._hydrate_conversation(convo)
        detail.participants = participants
        detail.messages = messages
        return detail

    def set_follow_up(
        self,
        conversation_id: int,
        follow_up_at: datetime | None,
        note: str | None,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET follow_up_at = %s, follow_up_note = %s, updated_at = now()
                WHERE tenant_id = %s AND id = %s
                """,
                (follow_up_at, note, self._tenant_id, conversation_id),
            )

    def mark_escalated(
        self,
        conversation_id: int,
        *,
        is_escalated: bool,
        reason: str | None,
        escalate_to: str | None,
    ) -> None:
        metadata_updates: dict[str, Any] = {}
        if escalate_to:
            metadata_updates["escalated_to"] = escalate_to
        assignments: list[sql.Composable] = [
            sql.SQL("{} = %s").format(sql.Identifier("is_escalated")),
            sql.SQL("{} = %s").format(sql.Identifier("escalation_reason")),
        ]
        params: list[Any] = [is_escalated, reason]
        if metadata_updates:
            assignments.append(sql.SQL("metadata = metadata || %s"))
            params.append(Jsonb(metadata_updates))
        params.extend((self._tenant_id, conversation_id))
        set_clause = sql.SQL(", ").join(
            assignments
            + [sql.SQL("escalated_at = now()"), sql.SQL("updated_at = now()")]
        )
        query = sql.SQL(
            "UPDATE conversations SET {} WHERE tenant_id = %s AND id = %s"
        ).format(set_clause)
        with self._cursor() as cur:
            cur.execute(query, params)

    def analytics(self, agent_id: int) -> schemas.ConversationAnalytics:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'open') AS open,
                    COUNT(*) FILTER (WHERE is_escalated) AS escalated,
                    COUNT(*) FILTER (WHERE follow_up_at IS NOT NULL AND follow_up_at > now()) AS follow_ups
                FROM conversations
                WHERE tenant_id = %s AND agent_id = %s
                """,
                (self._tenant_id, agent_id),
            )
            row = cur.fetchone() or {"open": 0, "escalated": 0, "follow_ups": 0}
        return schemas.ConversationAnalytics(
            open_conversations=row["open"],
            escalated_conversations=row["escalated"],
            pending_follow_ups=row["follow_ups"],
        )

    def channel_analytics(self, agent_id: int) -> list[schemas.ChannelConfigAnalytics]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT channel,
                       COUNT(*) AS conversations,
                       COUNT(*) FILTER (WHERE is_escalated) AS escalations,
                       MAX(last_message_at) AS last_activity
                FROM conversations
                WHERE tenant_id = %s AND agent_id = %s
                GROUP BY channel
                ORDER BY channel
                """,
                (self._tenant_id, agent_id),
            )
            rows = cur.fetchall()
        return [schemas.ChannelConfigAnalytics(**row) for row in rows]

    # Helpers ------------------------------------------------------------------
    def _hydrate_conversation(self, row: dict[str, Any]) -> schemas.ConversationDetail:
        data = dict(row)
        detail = schemas.ConversationDetail(**data)
        detail.participants = []
        detail.messages = []
        return detail
