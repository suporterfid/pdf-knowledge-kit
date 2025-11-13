"""Base abstractions for chat channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any

from ..conversations.models import NormalizedMessage


class ChannelAdapter(ABC):
    """Abstract base class encapsulating channel-specific behaviour."""

    #: Lowercase channel identifier used in routes and configuration.
    channel_name: str

    def __init__(self, *, agent_id: int) -> None:
        self.agent_id = agent_id

    @abstractmethod
    def parse_incoming(
        self,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        config: Mapping[str, Any],
    ) -> Iterable[NormalizedMessage]:
        """Convert a webhook payload into normalized messages."""

    def verify_signature(
        self,
        body: bytes,
        headers: Mapping[str, str],
        config: Mapping[str, Any],
    ) -> bool:
        """Validate authenticity of the webhook payload.

        Adapters can override this to implement signature checks. The default
        implementation returns ``True``.
        """

        return True

    def build_outgoing_payload(
        self, message: dict[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Prepare an outbound payload for the channel API.

        The default implementation simply returns the message unchanged.
        """

        return message
