"""Pydantic schemas for chat session management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a chat session."""

    id: str | None = None
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionCreate(BaseModel):
    """Request to create a new chat session."""

    title: str | None = None


class ChatSessionUpdate(BaseModel):
    """Request to update a chat session."""

    title: str | None = None


class ChatSessionDetail(BaseModel):
    """Full chat session with all messages."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionSummary(BaseModel):
    """Summary of a chat session for listing."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str | None = None


class ChatSessionList(BaseModel):
    """List of chat sessions."""

    items: list[ChatSessionSummary]
    total: int


class AddMessageRequest(BaseModel):
    """Request to add a message to a chat session."""

    role: str  # "user" or "assistant"
    content: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddMessageResponse(BaseModel):
    """Response after adding a message."""

    message: ChatMessage
    session: ChatSessionDetail
