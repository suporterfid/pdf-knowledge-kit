"""Helpers for parsing various document formats into text segments."""
from __future__ import annotations

from typing import Dict, Tuple

from .documents import read_docx_text, read_txt_text, read_csv_text, read_xlsx_text
from .html import extract_html_text
from .types import Chunk

ParsedSegment = Tuple[str, Dict[str, object]]

__all__ = [
    "Chunk",
    "ParsedSegment",
    "read_docx_text",
    "read_txt_text",
    "read_csv_text",
    "read_xlsx_text",
    "extract_html_text",
]
