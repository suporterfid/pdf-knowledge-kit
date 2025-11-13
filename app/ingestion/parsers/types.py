from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """Represents a chunk of text plus metadata for ingestion."""

    content: str
    source_path: str
    mime_type: str
    page_number: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """Return a metadata dictionary suitable for persistence."""

        metadata: dict[str, Any] = {
            "source_path": self.source_path,
            "mime_type": self.mime_type,
            "page_number": self.page_number,
            "sheet_name": self.sheet_name,
            "row_number": self.row_number,
        }
        if self.extra:
            metadata.update(self.extra)
        return {k: v for k, v in metadata.items() if v is not None}
