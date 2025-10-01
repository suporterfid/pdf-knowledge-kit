from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Chunk:
    """Represents a chunk of text plus metadata for ingestion."""

    content: str
    source_path: str
    mime_type: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> Dict[str, Any]:
        """Return a metadata dictionary suitable for persistence."""

        metadata: Dict[str, Any] = {
            "source_path": self.source_path,
            "mime_type": self.mime_type,
            "page_number": self.page_number,
            "sheet_name": self.sheet_name,
            "row_number": self.row_number,
        }
        if self.extra:
            metadata.update(self.extra)
        return {k: v for k, v in metadata.items() if v is not None}
