"""Telegram channel adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

from .base import ChannelAdapter
from ..conversations.models import NormalizedMessage


class TelegramAdapter(ChannelAdapter):
    channel_name = "telegram"

    def verify_signature(
        self,
        body: bytes,
        headers: Mapping[str, str],
        config: Mapping[str, Any],
    ) -> bool:
        secret = (config or {}).get("secret_token")
        if not secret:
            return True
        received = headers.get("X-Telegram-Bot-Api-Secret-Token")
        return bool(received and received == secret)

    def parse_incoming(
        self,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        config: Mapping[str, Any],
    ) -> Iterable[NormalizedMessage]:
        message = payload.get("message") or payload.get("edited_message")
        if message:
            yield self._from_message(message)
            return
        callback = payload.get("callback_query")
        if callback:
            data = callback.get("data") or ""
            message = callback.get("message") or {}
            chat = message.get("chat", {})
            user = callback.get("from") or {}
            sent_at = datetime.fromtimestamp(callback.get("date", datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
            yield NormalizedMessage(
                agent_id=self.agent_id,
                channel=self.channel_name,
                external_conversation_id=str(chat.get("id")),
                sender_id=str(user.get("id")),
                sender_role="customer",
                sender_name=self._display_name(user),
                text=data,
                attachments=[],
                metadata={"callback_query": callback},
                sent_at=sent_at,
            )

    def _from_message(self, message: Mapping[str, Any]) -> NormalizedMessage:
        chat = message.get("chat", {})
        user = message.get("from") or {}
        text = message.get("text") or message.get("caption") or ""
        attachments = []
        if message.get("photo"):
            attachments.append({"type": "photo", "sizes": message.get("photo")})
        if message.get("document"):
            attachments.append({"type": "document", **message.get("document")})
        if message.get("voice"):
            attachments.append({"type": "voice", **message.get("voice")})
        timestamp = message.get("date")
        if timestamp:
            sent_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            sent_at = datetime.now(timezone.utc)
        metadata: Dict[str, Any] = {
            "message_id": message.get("message_id"),
            "entities": message.get("entities"),
            "chat": chat,
        }
        return NormalizedMessage(
            agent_id=self.agent_id,
            channel=self.channel_name,
            external_conversation_id=str(chat.get("id")),
            sender_id=str(user.get("id")),
            sender_role="customer",
            sender_name=self._display_name(user),
            text=text,
            attachments=attachments,
            metadata=metadata,
            sent_at=sent_at,
        )

    def _display_name(self, user: Mapping[str, Any]) -> str:
        return user.get("username") or " ".join(
            filter(None, [user.get("first_name"), user.get("last_name")])
        ).strip()
