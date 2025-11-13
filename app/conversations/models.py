"""Domain models used by the conversation service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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
    sender_name: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: Optional[UUID] = None


@dataclass
class EscalationDecision:
    should_escalate: bool
    reason: Optional[str] = None
    escalate_to: Optional[str] = None


@dataclass
class FollowUpDecision:
    follow_up_at: Optional[datetime]
    note: Optional[str] = None
