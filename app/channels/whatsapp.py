"""WhatsApp channel adapter."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from ..conversations.models import NormalizedMessage
from .base import ChannelAdapter


class WhatsAppAdapter(ChannelAdapter):
    channel_name = "whatsapp"

    def verify_signature(
        self,
        body: bytes,
        headers: Mapping[str, str],
        config: Mapping[str, Any],
    ) -> bool:
        secret = (config or {}).get("webhook_secret")
        if not secret:
            return True
        received = headers.get("X-Hub-Signature-256")
        if not received:
            return False
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        return hmac.compare_digest(received, expected)

    def parse_incoming(
        self,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        config: Mapping[str, Any],
    ) -> Iterable[NormalizedMessage]:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = {c.get("wa_id"): c for c in value.get("contacts", [])}
                for message in value.get("messages", []):
                    sender_id = message.get("from") or ""
                    contact = contacts.get(sender_id, {})
                    name = contact.get("profile", {}).get("name")
                    text = ""
                    attachments = []
                    message_type = message.get("type")
                    if message_type == "text":
                        text = (message.get("text") or {}).get("body", "")
                    elif message_type in {"image", "audio", "video", "document"}:
                        media = message.get(message_type, {})
                        attachments.append({"type": message_type, **media})
                        text = media.get("caption", "")
                    elif message_type == "interactive":
                        interactive = message.get("interactive", {})
                        text = interactive.get("text") or interactive.get("title") or ""
                    conversation_id = (
                        (message.get("context") or {}).get("id")
                        or value.get("metadata", {}).get("phone_number_id")
                        or sender_id
                    )
                    timestamp = message.get("timestamp")
                    if timestamp:
                        try:
                            sent_at = datetime.fromtimestamp(
                                int(timestamp), tz=timezone.utc
                            )
                        except (ValueError, TypeError):
                            sent_at = datetime.now(timezone.utc)
                    else:
                        sent_at = datetime.now(timezone.utc)
                    metadata = {
                        "channel_payload": message,
                        "sender": contact,
                        "wa_business_account": value.get("metadata", {}),
                    }
                    yield NormalizedMessage(
                        agent_id=self.agent_id,
                        channel=self.channel_name,
                        external_conversation_id=str(conversation_id),
                        sender_id=str(sender_id),
                        sender_role="customer",
                        sender_name=name,
                        text=text,
                        attachments=attachments,
                        metadata=metadata,
                        sent_at=sent_at,
                    )
