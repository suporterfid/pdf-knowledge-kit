"""Pydantic schemas for conversation management APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConversationParticipant(BaseModel):
    id: int
    conversation_id: int
    role: str
    external_id: Optional[str] = None
    display_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationMessage(BaseModel):
    id: int
    conversation_id: int
    participant_id: Optional[int] = None
    direction: str
    body: Dict[str, Any] = Field(default_factory=dict)
    nlp: Dict[str, Any] = Field(default_factory=dict)
    sent_at: datetime


class ConversationSummary(BaseModel):
    id: int
    agent_id: int
    channel: str
    external_conversation_id: str
    status: str
    is_escalated: bool
    escalation_reason: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    follow_up_note: Optional[str] = None
    last_message_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationDetail(ConversationSummary):
    participants: List[ConversationParticipant] = Field(default_factory=list)
    messages: List[ConversationMessage] = Field(default_factory=list)


class ConversationList(BaseModel):
    items: List[ConversationSummary]
    total: int


class FollowUpRequest(BaseModel):
    follow_up_at: Optional[datetime] = None
    note: Optional[str] = None


class EscalationRequest(BaseModel):
    reason: Optional[str] = None
    escalate_to: Optional[str] = None
    note: Optional[str] = None


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
    last_activity: Optional[datetime] = None


class ConversationDashboardPayload(BaseModel):
    summary: ConversationAnalytics
    channels: List[ChannelConfigAnalytics]
    recent_conversations: List[ConversationSummary]
