"""Pydantic schemas for conversation management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConversationParticipant(BaseModel):
    id: int
    conversation_id: int
    role: str
    external_id: str | None = None
    display_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationMessage(BaseModel):
    id: int
    conversation_id: int
    participant_id: int | None = None
    direction: str
    body: dict[str, Any] = Field(default_factory=dict)
    nlp: dict[str, Any] = Field(default_factory=dict)
    sent_at: datetime


class ConversationSummary(BaseModel):
    id: int
    agent_id: int
    channel: str
    external_conversation_id: str
    status: str
    is_escalated: bool
    escalation_reason: str | None = None
    follow_up_at: datetime | None = None
    follow_up_note: str | None = None
    last_message_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationDetail(ConversationSummary):
    participants: list[ConversationParticipant] = Field(default_factory=list)
    messages: list[ConversationMessage] = Field(default_factory=list)


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total: int


class FollowUpRequest(BaseModel):
    follow_up_at: datetime | None = None
    note: str | None = None


class EscalationRequest(BaseModel):
    reason: str | None = None
    escalate_to: str | None = None
    note: str | None = None


class FollowUpResponse(ConversationDetail):
    pass


class EscalationResponse(ConversationDetail):
    pass


class MessageIngestResponse(BaseModel):
    conversation: ConversationDetail
    processed_messages: int


class ConversationAnalytics(BaseModel):
    open_conversations: int
    escalated_conversations: int
    pending_follow_ups: int


class ChannelConfigAnalytics(BaseModel):
    channel: str
    conversations: int
    escalations: int
    last_activity: datetime | None = None


class ConversationDashboardPayload(BaseModel):
    summary: ConversationAnalytics
    channels: list[ChannelConfigAnalytics]
    recent_conversations: list[ConversationSummary]
