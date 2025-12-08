"""Service layer for chat session management."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from . import chat_session_schemas as schemas
from .chat_session_repository import ChatSessionRepository


class ChatSessionService:
    """Orchestrates chat session operations."""

    def __init__(self, repository: ChatSessionRepository) -> None:
        self._repository = repository

    def create_session(
        self, title: str | None = None, metadata: dict[str, Any] | None = None
    ) -> schemas.ChatSessionDetail:
        """Create a new chat session with a unique ID."""
        session_id = str(uuid4())
        return self._repository.create_session(session_id, title, metadata)

    def get_session(self, session_id: str) -> schemas.ChatSessionDetail | None:
        """Retrieve a chat session by ID."""
        return self._repository.get_session(session_id)

    def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[schemas.ChatSessionSummary], int]:
        """List all chat sessions for the tenant."""
        return self._repository.list_sessions(limit, offset)

    def update_session(
        self, session_id: str, title: str | None = None
    ) -> schemas.ChatSessionDetail | None:
        """Update a chat session."""
        return self._repository.update_session(session_id, title)

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        return self._repository.delete_session(session_id)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> schemas.AddMessageResponse:
        """Add a message to a chat session."""
        message_id = str(uuid4())
        message = self._repository.add_message(
            session_id, message_id, role, content, sources, metadata
        )
        session = self._repository.get_session(session_id)
        if not session:
            raise RuntimeError(f"Session {session_id} not found after adding message")
        return schemas.AddMessageResponse(message=message, session=session)

    def clear_session_messages(self, session_id: str) -> bool:
        """Clear all messages from a chat session."""
        return self._repository.clear_session_messages(session_id)
