"""High-level conversation flow orchestration."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from ..agents import schemas as agent_schemas
from ..nlp import NlpPipeline
from . import schemas
from .models import EscalationDecision, FollowUpDecision, NormalizedMessage
from .repository import ConversationRepository


class ConversationService:
    """Coordinates persistence, NLP enrichment and follow-up logic."""

    def __init__(
        self,
        repository: ConversationRepository,
        *,
        tenant_id: UUID | None = None,
        nlp_pipeline: NlpPipeline | None = None,
    ) -> None:
        self._repository = repository
        self._tenant_id = tenant_id or getattr(repository, "tenant_id", None)
        self._nlp = nlp_pipeline or NlpPipeline()

    # ------------------------------------------------------------------
    # Incoming message processing

    def process_incoming_message(
        self,
        agent: agent_schemas.AgentDetail,
        normalized: NormalizedMessage,
        channel_config: dict[str, Any] | None = None,
    ) -> schemas.MessageIngestResponse:
        """Persist a message and update the conversation state."""

        tenant_id = normalized.tenant_id or self._tenant_id or agent.tenant_id
        normalized.tenant_id = tenant_id

        conversation = self._repository.get_by_external(
            agent.id, normalized.channel, normalized.external_conversation_id
        )
        if not conversation:
            conversation = self._repository.create_conversation(
                agent.id,
                normalized.channel,
                normalized.external_conversation_id,
                metadata={"channel_config": channel_config or {}},
            )
        participant = self._repository.get_participant(
            conversation.id, normalized.sender_role, normalized.sender_id
        )
        if not participant:
            participant = self._repository.add_participant(
                conversation.id,
                normalized.sender_role,
                normalized.sender_id,
                normalized.sender_name,
                metadata=normalized.metadata.get("sender"),
            )
        nlp = self._nlp.analyse(normalized.text)
        body = {
            "text": normalized.text,
            "attachments": normalized.attachments,
            "metadata": normalized.metadata,
        }
        self._repository.add_message(
            conversation.id,
            participant.id if participant else None,
            direction="inbound",
            body=body,
            nlp=nlp,
            sent_at=normalized.sent_at,
        )
        metadata = dict(conversation.metadata)
        metadata.setdefault("messages_ingested", 0)
        metadata["messages_ingested"] += 1
        decision = self._evaluate_escalation(nlp, normalized.metadata, channel_config)
        follow_up = self._evaluate_follow_up(nlp, normalized.metadata)
        if decision.should_escalate:
            self._repository.mark_escalated(
                conversation.id,
                is_escalated=True,
                reason=decision.reason,
                escalate_to=decision.escalate_to,
            )
            metadata.setdefault("escalations", []).append(
                {
                    "reason": decision.reason,
                    "escalate_to": decision.escalate_to,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
        if follow_up.follow_up_at:
            self._repository.set_follow_up(
                conversation.id,
                follow_up.follow_up_at,
                follow_up.note,
            )
            metadata.setdefault("follow_ups", []).append(
                {
                    "scheduled_for": follow_up.follow_up_at.isoformat(),
                    "note": follow_up.note,
                }
            )
        self._repository.update_conversation_touch(
            conversation.id,
            last_message_at=normalized.sent_at,
            metadata=metadata,
        )
        refreshed = self._repository.get_conversation(conversation.id)
        if refreshed is None:
            raise RuntimeError(
                "Conversation disappeared after persisting inbound message"
            )
        return schemas.MessageIngestResponse(
            conversation=refreshed, processed_messages=1
        )

    # ------------------------------------------------------------------
    # Queries

    def list_conversations(
        self, agent_id: int, limit: int = 50
    ) -> schemas.ConversationList:
        items = self._repository.list_conversations(agent_id, limit=limit)
        return schemas.ConversationList(items=items, total=len(items))

    def get_conversation(self, conversation_id: int) -> schemas.ConversationDetail:
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        return conversation

    def dashboard_snapshot(
        self, agent_id: int, limit: int = 10
    ) -> schemas.ConversationDashboardPayload:
        summary = self._repository.analytics(agent_id)
        channels = self._repository.channel_analytics(agent_id)
        recent = self._repository.list_conversations(agent_id, limit=limit)
        return schemas.ConversationDashboardPayload(
            summary=summary,
            channels=channels,
            recent_conversations=recent,
        )

    # ------------------------------------------------------------------
    # Actions

    def schedule_follow_up(
        self,
        conversation_id: int,
        follow_up_at: datetime | None,
        note: str | None,
    ) -> schemas.ConversationDetail:
        self._repository.set_follow_up(conversation_id, follow_up_at, note)
        return self.get_conversation(conversation_id)

    def escalate(
        self,
        conversation_id: int,
        reason: str | None,
        escalate_to: str | None,
    ) -> schemas.ConversationDetail:
        self._repository.mark_escalated(
            conversation_id,
            is_escalated=True,
            reason=reason,
            escalate_to=escalate_to,
        )
        return self.get_conversation(conversation_id)

    def resolve_escalation(self, conversation_id: int) -> schemas.ConversationDetail:
        self._repository.mark_escalated(
            conversation_id,
            is_escalated=False,
            reason=None,
            escalate_to=None,
        )
        return self.get_conversation(conversation_id)

    # ------------------------------------------------------------------
    # Helpers

    def _evaluate_escalation(
        self,
        nlp: dict[str, Any],
        metadata: dict[str, Any],
        channel_config: dict[str, Any] | None,
    ) -> EscalationDecision:
        escalate_flag = metadata.get("escalate") or metadata.get("escalation_required")
        if escalate_flag:
            return EscalationDecision(
                True, reason="channel_flag", escalate_to=metadata.get("target")
            )
        sentiment = nlp.get("sentiment", {})
        intent = nlp.get("intent", {})
        min_score = (
            (channel_config or {})
            .get("escalation", {})
            .get("sentiment_threshold", 0.75)
        )
        escalate_to = (channel_config or {}).get("escalation", {}).get("default_queue")
        if intent.get("label") in {"complaint", "cancellation"}:
            return EscalationDecision(
                True, reason=intent.get("label"), escalate_to=escalate_to
            )
        if (
            sentiment.get("label") == "negative"
            and sentiment.get("score", 0) >= min_score
        ):
            return EscalationDecision(
                True, reason="negative_sentiment", escalate_to=escalate_to
            )
        return EscalationDecision(False)

    def _evaluate_follow_up(
        self, nlp: dict[str, Any], metadata: dict[str, Any]
    ) -> FollowUpDecision:
        if metadata.get("follow_up_at"):
            return FollowUpDecision(
                metadata["follow_up_at"], metadata.get("follow_up_note")
            )
        intent = nlp.get("intent", {})
        if intent.get("label") in {"support_followup", "callback_request"}:
            follow_up_at = datetime.now(timezone.utc) + timedelta(hours=24)
            return FollowUpDecision(follow_up_at, note="Automatic follow-up scheduled")
        entities: Iterable[dict[str, Any]] = nlp.get("entities", [])
        for entity in entities:
            if entity.get("type") == "datetime" and entity.get("value"):
                value = entity.get("value")
                if isinstance(value, str):
                    try:
                        parsed = datetime.fromisoformat(value)
                    except ValueError:
                        continue
                elif isinstance(value, datetime):
                    parsed = value
                else:
                    continue
                return FollowUpDecision(parsed, note="Entity derived follow-up")
        return FollowUpDecision(None)
