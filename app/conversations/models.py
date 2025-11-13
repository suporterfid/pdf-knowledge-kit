"""Domain models used by the conversation service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass
class NormalizedMessage:
    """Uniform representation of inbound channel messages."""

    agent_id: int
    channel: str
    external_conversation_id: str
    sender_id: str
    sender_role: str
    text: str
    sender_name: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: UUID | None = None


@dataclass
class EscalationDecision:
    should_escalate: bool
    reason: str | None = None
    escalate_to: str | None = None


@dataclass
class FollowUpDecision:
    follow_up_at: datetime | None
    note: str | None = None
