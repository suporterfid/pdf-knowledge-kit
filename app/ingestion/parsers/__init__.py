"""Helpers for parsing various document formats into text segments."""

from __future__ import annotations

from .documents import read_csv_text, read_docx_text, read_txt_text, read_xlsx_text
from .html import extract_html_text
from .types import Chunk

ParsedSegment = tuple[str, dict[str, object]]

__all__ = [
    "Chunk",
    "ParsedSegment",
    "read_docx_text",
    "read_txt_text",
    "read_csv_text",
    "read_xlsx_text",
    "extract_html_text",
]
