"""Connector abstractions for external data sources."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..parsers import Chunk


@dataclass(slots=True)
class ConnectorRecord:
    """Represents a document worth of chunks produced by a connector."""

    document_path: str
    chunks: list[Chunk]
    bytes_len: int
    page_count: int = 1
    document_sync_state: dict[str, object] | None = None
    extra_info: dict[str, object] = field(default_factory=dict)


__all__ = ["ConnectorRecord"]
