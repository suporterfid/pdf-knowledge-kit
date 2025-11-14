"""CLI wrapper for :mod:`app.ingestion.service`.

This module preserves the old ``ingest.py`` command line interface while
delegating all functionality to :mod:`app.ingestion.service`.  When imported
as ``ingest`` it simply re-exports the service module for backward
compatibility.  When executed as a script it parses the legacy CLI arguments
and forwards the work to the new service functions.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path

from app.ingestion import service as _service


def _iter_docs(doc_path: Path) -> list[Path]:
    """Yield Markdown and PDF files from ``doc_path`` recursively."""

    exts = {".pdf", ".md"}
    if doc_path.is_file() and doc_path.suffix.lower() in exts:
        return [doc_path]
    files: list[Path] = []
    for p in sorted(doc_path.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
    return files


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and execute the requested ingestion tasks."""

    parser = argparse.ArgumentParser(description="Ingest documents and URLs")
    parser.add_argument(
        "--docs",
        default=os.getenv("DOCS_DIR"),
        help="Directory containing PDFs/Markdown files",
    )
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        default=[],
        help="URL to ingest (may be specified multiple times)",
    )
    parser.add_argument(
        "--urls-file",
        default=os.getenv("URLS_FILE"),
        help="File with URLs to ingest, one per line",
    )
    parser.add_argument(
        "--reindex",
        help="Reindex an existing source by UUID",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        default=os.getenv("ENABLE_OCR") == "1",
        help="Enable OCR for PDFs without embedded text",
    )
    parser.add_argument(
        "--ocr-lang",
        default=os.getenv("OCR_LANG"),
        help="Languages for Tesseract OCR (e.g., eng+por)",
    )
    parser.add_argument(
        "--tenant-id",
        default=os.getenv("TENANT_ID"),
        help="Tenant identifier (UUID)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("ingest")

    tenant_id = args.tenant_id
    if not tenant_id:
        parser.error("--tenant-id is required (or set TENANT_ID)")

    if args.docs:
        doc_dir = Path(args.docs)
        for doc in _iter_docs(doc_dir):
            log.info("ingesting %s", doc)
            doc_job_id = _service.ingest_local(
                doc,
                tenant_id=tenant_id,
                use_ocr=args.ocr,
                ocr_lang=args.ocr_lang,
            )
            _service.wait_for_job(doc_job_id)

    urls: list[str] = list(args.urls)
    if args.urls_file:
        path = Path(args.urls_file)
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        urls.append(line)
    if urls:
        log.info("ingesting %d url(s)", len(urls))
        urls_job_id = _service.ingest_urls(urls, tenant_id=tenant_id)
        _service.wait_for_job(urls_job_id)

    if args.reindex:
        try:
            source_id = uuid.UUID(args.reindex)
        except ValueError:
            log.error("--reindex requires a valid UUID")
        else:
            reindex_job_id = _service.reindex_source(source_id, tenant_id=tenant_id)
            if reindex_job_id is None:
                log.error("source %s could not be reindexed", source_id)
            else:
                _service.wait_for_job(reindex_job_id)


if __name__ != "__main__":  # pragma: no cover - import-time aliasing
    # When imported, expose the service module directly for compatibility.
    sys.modules[__name__] = _service
else:  # pragma: no cover - CLI execution
    main()
