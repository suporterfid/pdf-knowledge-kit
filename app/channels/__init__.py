"""Channel adapter registry for multi-channel messaging support."""
from __future__ import annotations

from typing import Dict, Type

from .base import ChannelAdapter
from .telegram import TelegramAdapter
from .whatsapp import WhatsAppAdapter

_REGISTRY: Dict[str, Type[ChannelAdapter]] = {}


def register_adapter(adapter: Type[ChannelAdapter]) -> None:
    """Register a channel adapter class in the global registry."""
    _REGISTRY[adapter.channel_name] = adapter


def get_adapter(name: str) -> Type[ChannelAdapter]:
    """Retrieve an adapter class for ``name`` or raise ``KeyError``."""
    normalized = name.lower()
    if normalized not in _REGISTRY:
        raise KeyError(f"Channel '{name}' is not configured")
    return _REGISTRY[normalized]


# Pre-register built-in adapters
register_adapter(WhatsAppAdapter)
register_adapter(TelegramAdapter)

__all__ = ["ChannelAdapter", "get_adapter", "register_adapter"]
