"""Connector abstractions for external data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..parsers import Chunk


@dataclass(slots=True)
class ConnectorRecord:
    """Represents a document worth of chunks produced by a connector."""

    document_path: str
    chunks: List[Chunk]
    bytes_len: int
    page_count: int = 1
    document_sync_state: Dict[str, object] | None = None
    extra_info: Dict[str, object] = field(default_factory=dict)


__all__ = ["ConnectorRecord"]

