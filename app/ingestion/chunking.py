"""Utilities for transforming raw text into embedding-ready chunks."""

from __future__ import annotations

from typing import Dict, List

from .parsers import Chunk


def chunk_text(
    text: str,
    *,
    source_path: str,
    mime_type: str,
    page_number: int | None = None,
    sheet_name: str | None = None,
    row_number: int | None = None,
    extra_metadata: Dict[str, object] | None = None,
    max_chars: int = 1200,
    overlap: int = 200,
) -> List[Chunk]:
    """Split text into :class:`Chunk` objects with optional metadata."""

    if not text:
        return []
    text = text.replace("\r", "")
    parts = text.split("\n\n")
    text_chunks: List[str] = []
    buf = ""
    for part in parts:
        if len(buf) + len(part) + 2 <= max_chars:
            buf += (("\n\n" if buf else "") + part)
        else:
            if buf:
                text_chunks.append(buf.strip())
            buf = part
            while len(buf) > max_chars:
                text_chunks.append(buf[:max_chars].strip())
                buf = buf[max_chars - overlap:]
    if buf:
        text_chunks.append(buf.strip())

    normalized: List[str] = []
    for i, ch in enumerate(text_chunks):
        if i == 0:
            normalized.append(ch)
        else:
            prev = normalized[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            merged = (tail + "\n\n" + ch).strip() if tail else ch
            normalized.append(merged if len(merged) <= max_chars + overlap else ch)

    extra = dict(extra_metadata or {})
    return [
        Chunk(
            content=chunk_text,
            source_path=source_path,
            mime_type=mime_type,
            page_number=page_number,
            sheet_name=sheet_name,
            row_number=row_number,
            extra=extra,
        )
        for chunk_text in normalized
    ]


__all__ = ["chunk_text"]

