"""High‑level ingestion service and helpers for the knowledge base.

Responsibilities
----------------
- Ensure database schema/migrations are applied (idempotent).
- Read and normalize content from Markdown/PDF (with optional OCR) and URLs.
- Chunk text with overlap, embed using fastembed, and persist to Postgres
  (documents/chunks with a pgvector column for embeddings).
- Track ingestion as background jobs with on-disk logs for progress/debugging.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple
from contextlib import contextmanager

import requests
from fastembed import TextEmbedding
import embedding  # attempts to register custom CLS-pooled model (no-op if unsupported)
from pdf2image import convert_from_path
from pypdf import PdfReader
import pytesseract
import psycopg
from pgvector.psycopg import register_vector

from . import storage
from .models import ChunkMetadata, Job, JobLogSlice, JobStatus, Source, SourceType
from .runner import IngestionRunner
from .parsers import (
    Chunk,
    ParsedSegment,
    extract_html_text,
    read_csv_text,
    read_docx_text,
    read_txt_text,
    read_xlsx_text,
)
from .chunking import chunk_text
from .connectors import ConnectorRecord
from .connectors.rest import RestConnector
from .connectors.sql import SqlConnector
from .connectors.transcription import TranscriptionConnector

# Multilingual embedding model
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2-cls"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"

_PDF_SEGMENT_CACHE: Dict[Tuple[str, bool, str | None], List[ParsedSegment]] = {}


def _pdf_cache_key(pdf_path: Path, use_ocr: bool, ocr_lang: str | None) -> Tuple[str, bool, str | None]:
    resolved = str(pdf_path.resolve())
    if not use_ocr:
        return (resolved, False, None)
    effective = ocr_lang or os.getenv("OCR_LANG") or "eng+por+spa"
    return (resolved, True, effective)


def _resolve_pdf_segments(
    pdf_path: Path, use_ocr: bool, ocr_lang: str | None
) -> List[ParsedSegment]:
    key = _pdf_cache_key(pdf_path, use_ocr, ocr_lang)
    cached = _PDF_SEGMENT_CACHE.get(key)
    if cached is not None:
        return cached

    # ``read_pdf_text`` populates the cache and remains the public API used by tests.
    _ = read_pdf_text(pdf_path, use_ocr=use_ocr, ocr_lang=ocr_lang)
    cached = _PDF_SEGMENT_CACHE.get(key)
    if cached is not None:
        return cached

    # Fallback: in case ``read_pdf_text`` was patched or cleared the cache unexpectedly.
    segments = _read_pdf_segments(pdf_path, use_ocr=use_ocr, ocr_lang=ocr_lang)
    _PDF_SEGMENT_CACHE[key] = segments
    return segments

# ---------------------------------------------------------------------------
# Helper functions moved from the legacy ``ingest.py`` script
# ---------------------------------------------------------------------------

def read_md_text(md_path: Path) -> str:
    """Read a Markdown file with reasonable encoding fallbacks."""
    for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16le", "utf-16be", "latin-1"):
        try:
            with md_path.open("r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    try:  # last resort: best-effort decode
        with md_path.open("rb") as f:
            return f.read().decode("utf-8", errors="ignore")
    except Exception as e:  # pragma: no cover - defensive
        print(f"[WARN] Falha ao ler {md_path}: {e}")
        return ""


def _read_pdf_segments(
    pdf_path: Path, use_ocr: bool = False, ocr_lang: str | None = None
) -> List[ParsedSegment]:
    segments: List[ParsedSegment] = []
    try:
        reader = PdfReader(str(pdf_path))
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            segments.append((text, {"mime_type": "application/pdf", "page_number": idx}))

        if any(text.strip() for text, _ in segments):
            return segments

        if use_ocr:
            try:
                ocr_lang = ocr_lang or os.getenv("OCR_LANG") or "eng+por+spa"
                available_langs = set(pytesseract.get_languages(config=""))
                requested_langs = {lang.strip() for lang in ocr_lang.split("+") if lang.strip()}
                missing_langs = requested_langs - available_langs
                if missing_langs:
                    print(f"[WARN] Missing OCR language(s): {', '.join(sorted(missing_langs))}")

                images = convert_from_path(str(pdf_path))
                ocr_segments: List[ParsedSegment] = []
                for idx, img in enumerate(images, start=1):
                    try:
                        txt = pytesseract.image_to_string(img, lang=ocr_lang)
                    except Exception:
                        txt = ""
                    ocr_segments.append((txt, {"mime_type": "application/pdf", "page_number": idx}))
                return ocr_segments
            except Exception as e:
                print(f"[WARN] Falha no OCR para {pdf_path}: {e}")
                return segments
        return segments
    except Exception as e:
        print(f"[WARN] Falha ao ler {pdf_path}: {e}")
        return []


def read_pdf_text(pdf_path: Path, use_ocr: bool = False, ocr_lang: str | None = None) -> str:
    key = _pdf_cache_key(pdf_path, use_ocr, ocr_lang)
    segments = _read_pdf_segments(pdf_path, use_ocr=use_ocr, ocr_lang=ocr_lang)
    _PDF_SEGMENT_CACHE[key] = segments
    return "\n".join(text for text, _ in segments)


def read_url_text(url: str) -> str:
    """Fetch a URL and return readable text content."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return extract_html_text(resp.text)
    except Exception as e:
        print(f"[WARN] Falha ao ler URL {url}: {e}")
        return ""


def ensure_schema(
    conn: psycopg.Connection,
    schema_sql_path: Path = SCHEMA_PATH,
    migrations_dir: Path | None = None,
) -> None:
    """Ensure the required tables and migrations exist.

    This function is *non-destructive*; it executes the base schema and any
    migrations, relying on ``IF NOT EXISTS`` clauses so that existing tables or
    columns are preserved. It can safely be called multiple times.

    Parameters
    ----------
    conn:
        Active database connection.
    schema_sql_path:
        Path to the ``schema.sql`` file containing the initial schema. Defaults
        to ``SCHEMA_PATH``.
    migrations_dir:
        Directory containing sequential ``.sql`` migration files. If not
        provided, ``schema_sql_path.parent / 'migrations'`` is used. Each
        migration is executed in alphabetical order.
    """

    with conn.cursor() as cur:
        cur.execute(schema_sql_path.read_text(encoding="utf-8"))

        migrations_dir = migrations_dir or schema_sql_path.parent / "migrations"
        if migrations_dir.exists():
            for mig in sorted(migrations_dir.glob("*.sql")):
                cur.execute(mig.read_text(encoding="utf-8"))

    conn.commit()


def reset_schema(
    conn: psycopg.Connection,
    schema_sql_path: Path = SCHEMA_PATH,
    migrations_dir: Path | None = None,
) -> None:
    """Drop ingestion tables and recreate them.

    This helper is intended for tests or development scenarios where a clean
    slate is required. After dropping tables it delegates to ``ensure_schema``
    to recreate them and apply migrations.
    """

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS ingestion_jobs CASCADE")
        cur.execute("DROP TABLE IF EXISTS sources CASCADE")
        cur.execute("DROP TABLE IF EXISTS chunks CASCADE")
        cur.execute("DROP TABLE IF EXISTS documents CASCADE")
    conn.commit()
    ensure_schema(conn, schema_sql_path, migrations_dir)


@contextmanager
def connect_and_init(db_url: str):
    """Connect to the database, ensure schema, then register pgvector.

    Ensures ``ensure_schema`` runs before ``register_vector`` for every
    connection.
    """

    with psycopg.connect(db_url) as conn:
        ensure_schema(conn)
        register_vector(conn)
        yield conn


def upsert_document(
    conn: psycopg.Connection,
    path: str | Path,
    bytes_len: int,
    page_count: int,
    *,
    source_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Create or update a document and return its identifier."""

    version = storage.upsert_document(
        conn,
        path=str(path),
        bytes_len=bytes_len,
        page_count=page_count,
        source_id=source_id,
    )
    return version.document_id


def insert_chunks(
    conn: psycopg.Connection,
    doc_id: uuid.UUID,
    chunks: Sequence[Chunk],
    embeddings: Sequence[list[float]],
) -> None:
    """Insert chunk rows with embeddings; ignore duplicates by (doc_id, index)."""

    metadata_payloads = [
        ChunkMetadata(
            source_path=chunk.source_path,
            mime_type=chunk.mime_type,
            page_number=chunk.page_number,
            sheet_name=chunk.sheet_name,
            row_number=chunk.row_number,
            extra=chunk.extra or None,
        )
        for chunk in chunks
    ]
    storage.insert_chunks(
        conn,
        document_id=doc_id,
        chunks=[chunk.content for chunk in chunks],
        embeddings=embeddings,
        metadatas=metadata_payloads,
    )


def _process_connector_stream(
    conn: psycopg.Connection,
    *,
    source: Source,
    connector: Any,
    embedder: TextEmbedding,
    cancel_event,
    logger: logging.Logger,
    job_id: uuid.UUID,
) -> tuple[int, int, bool]:
    """Stream records from a connector, embed them and persist to storage."""

    documents = 0
    chunks_total = 0
    canceled = False

    for record in connector.stream(cancel_event):
        if cancel_event.is_set():
            canceled = True
            break
        if not isinstance(record, ConnectorRecord):
            continue
        if not record.chunks:
            continue

        texts_for_embedding = [chunk.content for chunk in record.chunks if chunk.content]
        embeddings: list[list[float]] = []
        if texts_for_embedding:
            for emb in embedder.embed(texts_for_embedding):
                if cancel_event.is_set():
                    canceled = True
                    break
                embeddings.append(emb)
        if canceled:
            break

        version = storage.upsert_document(
            conn,
            path=str(record.document_path),
            bytes_len=record.bytes_len,
            page_count=record.page_count,
            source_id=source.id,
            connector_type=source.connector_type or source.type.value,
            sync_state=record.document_sync_state,
        )
        insert_chunks(conn, version.document_id, record.chunks, embeddings)
        documents += 1
        chunks_total += len(record.chunks)
        logger.info("document=%s chunks=%d", record.document_path, len(record.chunks))

    if not canceled:
        next_state = getattr(connector, "next_sync_state", None)
        if next_state is not None:
            storage.update_source_sync_state(conn, source.id, sync_state=next_state)
        job_params = dict(getattr(connector, "job_metadata", {}))
        job_params.update({"documents": documents, "chunks": chunks_total})
        storage.update_job_params(conn, job_id, job_params)

    return documents, chunks_total, canceled

# ---------------------------------------------------------------------------
# High level service API
# ---------------------------------------------------------------------------

_runner = IngestionRunner()


def _setup_job_logging(job_id: uuid.UUID) -> tuple[logging.Logger, Path]:
    """Create a dedicated logger + file for a job and return them."""
    log_dir = Path("logs/jobs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job_id}.log"
    logger = logging.getLogger(f"ingestion.{job_id}")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    logger.addHandler(fh)
    return logger, log_path


def ingest_source(source_id: uuid.UUID) -> uuid.UUID:
    """Ingest a connector-backed source such as a database or REST API."""

    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    with connect_and_init(db_url) as conn:
        source = storage.get_source(conn, source_id)
        if not source:
            raise ValueError(f"source {source_id} not found")
        if source.type not in {
            SourceType.DATABASE,
            SourceType.API,
            SourceType.AUDIO_TRANSCRIPT,
            SourceType.VIDEO_TRANSCRIPT,
        }:
            raise ValueError(
                "ingest_source only supports database, api, and transcription types, "
                f"got {source.type.value}"
            )
        job_id = storage.create_job(
            conn,
            source_id,
            params={
                "source_type": source.type.value,
                "provider": (source.params or {}).get("provider") if source.params else None,
            },
        )

    logger, log_path = _setup_job_logging(job_id)

    def _work(cancel_event):
        try:
            with connect_and_init(db_url) as conn:
                storage.update_job_status(
                    conn,
                    job_id,
                    JobStatus.RUNNING,
                    started_at=datetime.utcnow(),
                    log_path=str(log_path),
                )

                source = storage.get_source(conn, source_id)
                if not source:
                    raise ValueError(f"source {source_id} not found")

                try:
                    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
                except Exception:
                    embedder = TextEmbedding(
                        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                    )

                documents = 0
                chunks_total = 0
                canceled = False

                if source.type == SourceType.DATABASE:
                    connector = SqlConnector(source, logger=logger)
                    documents, chunks_total, canceled = _process_connector_stream(
                        conn,
                        source=source,
                        connector=connector,
                        embedder=embedder,
                        cancel_event=cancel_event,
                        logger=logger,
                        job_id=job_id,
                    )
                elif source.type == SourceType.API:
                    connector = RestConnector(source, logger=logger)
                    documents, chunks_total, canceled = _process_connector_stream(
                        conn,
                        source=source,
                        connector=connector,
                        embedder=embedder,
                        cancel_event=cancel_event,
                        logger=logger,
                        job_id=job_id,
                    )
                elif source.type in {SourceType.AUDIO_TRANSCRIPT, SourceType.VIDEO_TRANSCRIPT}:
                    connector = TranscriptionConnector(source, logger=logger)
                    documents, chunks_total, canceled = _process_connector_stream(
                        conn,
                        source=source,
                        connector=connector,
                        embedder=embedder,
                        cancel_event=cancel_event,
                        logger=logger,
                        job_id=job_id,
                    )
                else:
                    raise ValueError(
                        "ingest_source only supports database, api, and transcription types, "
                        f"got {source.type.value}"
                    )

                if cancel_event.is_set() or canceled:
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.CANCELED,
                        finished_at=datetime.utcnow(),
                    )
                    return

                logger.info(
                    "ingestion complete documents=%d chunks=%d", documents, chunks_total
                )
                storage.update_job_status(
                    conn,
                    job_id,
                    JobStatus.SUCCEEDED,
                    finished_at=datetime.utcnow(),
                )
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("ingestion failed: %s", e)
            try:
                with psycopg.connect(db_url) as conn:
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.FAILED,
                        error=str(e),
                        finished_at=datetime.utcnow(),
                    )
            finally:
                pass
        finally:
            for h in list(logger.handlers):
                h.close()
                logger.removeHandler(h)
            _runner.clear(job_id)

    _runner.submit(job_id, _work)
    return job_id


def ingest_local(path: Path, *, use_ocr: bool = False, ocr_lang: str | None = None) -> uuid.UUID:
    """Ingest a local Markdown or PDF file as a background job."""

    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    with connect_and_init(db_url) as conn:
        source_id = storage.get_or_create_source(conn, type=SourceType.LOCAL_DIR, path=str(path))
        job_id = storage.create_job(conn, source_id)

    logger, log_path = _setup_job_logging(job_id)

    def _work(cancel_event):
        try:
            with connect_and_init(db_url) as conn:
                storage.update_job_status(
                    conn,
                    job_id,
                    JobStatus.RUNNING,
                    started_at=datetime.utcnow(),
                    log_path=str(log_path),
                )

                registry: Dict[str, Callable[[], Sequence[ParsedSegment]]] = {
                    ".pdf": lambda: _resolve_pdf_segments(path, use_ocr, ocr_lang),
                    ".md": lambda: [
                        (
                            read_md_text(path),
                            {"mime_type": "text/markdown", "page_number": 1},
                        )
                    ],
                    ".txt": lambda: read_txt_text(path),
                    ".docx": lambda: read_docx_text(path),
                    ".csv": lambda: read_csv_text(path),
                    ".xlsx": lambda: read_xlsx_text(path),
                }
                suffix = path.suffix.lower()
                segments = registry.get(suffix, lambda: [])()

                def _calc_page_count(items: Sequence[ParsedSegment]) -> int:
                    page_numbers = [meta.get("page_number") for _, meta in items if meta.get("page_number")]
                    if page_numbers:
                        return int(max(page_numbers))
                    sheet_names = {
                        str(meta.get("sheet_name"))
                        for _, meta in items
                        if meta.get("sheet_name")
                    }
                    if sheet_names:
                        return len(sheet_names)
                    row_numbers = [meta.get("row_number") for _, meta in items if meta.get("row_number")]
                    if row_numbers:
                        return int(max(row_numbers))
                    return 1

                page_count = _calc_page_count(segments)

                if cancel_event.is_set():
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.CANCELED,
                        finished_at=datetime.utcnow(),
                    )
                    return

                chunks: List[Chunk] = []
                for text_segment, metadata in segments:
                    mime_type = str(metadata.get("mime_type") or "application/octet-stream")
                    extra_metadata = {
                        k: v
                        for k, v in metadata.items()
                        if k
                        not in {"mime_type", "page_number", "sheet_name", "row_number"}
                    }
                    chunks.extend(
                        chunk_text(
                            text_segment,
                            source_path=str(path),
                            mime_type=mime_type,
                            page_number=metadata.get("page_number"),
                            sheet_name=metadata.get("sheet_name"),
                            row_number=metadata.get("row_number"),
                            extra_metadata=extra_metadata,
                        )
                    )

                logger.info("chunks=%d", len(chunks))
                if cancel_event.is_set():
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.CANCELED,
                        finished_at=datetime.utcnow(),
                    )
                    return

                try:
                    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
                except Exception:
                    embedder = TextEmbedding(
                        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                    )
                texts_for_embedding = [chunk.content for chunk in chunks]
                embeddings: list[list[float]] = []
                if texts_for_embedding:
                    for emb in embedder.embed(texts_for_embedding):
                        if cancel_event.is_set():
                            storage.update_job_status(
                                conn,
                                job_id,
                                JobStatus.CANCELED,
                                finished_at=datetime.utcnow(),
                            )
                            return
                        embeddings.append(emb)

                bytes_len = path.stat().st_size if path.exists() else 0
                doc_id = upsert_document(conn, path, bytes_len, page_count, source_id=source_id)
                insert_chunks(conn, doc_id, chunks, embeddings)

                storage.update_job_status(
                    conn,
                    job_id,
                    JobStatus.SUCCEEDED,
                    finished_at=datetime.utcnow(),
                )
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("ingestion failed: %s", e)
            try:
                with psycopg.connect(db_url) as conn:
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.FAILED,
                        error=str(e),
                        finished_at=datetime.utcnow(),
                    )
            finally:
                pass
        finally:
            for h in list(logger.handlers):
                h.close()
                logger.removeHandler(h)
            _runner.clear(job_id)

    _runner.submit(job_id, _work)
    return job_id


def ingest_url(url: str) -> uuid.UUID:
    return ingest_urls([url])


def ingest_urls(urls: List[str]) -> uuid.UUID:
    """Ingest multiple public URLs as a background job."""
    if not urls:
        raise ValueError("no URLs provided")

    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    first_url = urls[0]
    with connect_and_init(db_url) as conn:
        source_id = storage.get_or_create_source(conn, type=SourceType.URL_LIST, url=first_url)
        job_id = storage.create_job(conn, source_id)

    logger, log_path = _setup_job_logging(job_id)

    def _work(cancel_event):
        try:
            with connect_and_init(db_url) as conn:
                storage.update_job_status(
                    conn,
                    job_id,
                    JobStatus.RUNNING,
                    started_at=datetime.utcnow(),
                    log_path=str(log_path),
                )

                try:
                    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
                except Exception:
                    embedder = TextEmbedding(
                        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                    )

                for url in urls:
                    if cancel_event.is_set():
                        storage.update_job_status(
                            conn,
                            job_id,
                            JobStatus.CANCELED,
                            finished_at=datetime.utcnow(),
                        )
                        return

                    storage.get_or_create_source(conn, type=SourceType.URL, url=url)
                    text = read_url_text(url)
                    if cancel_event.is_set():
                        storage.update_job_status(
                            conn,
                            job_id,
                            JobStatus.CANCELED,
                            finished_at=datetime.utcnow(),
                        )
                        return

                    chunks = chunk_text(
                        text,
                        source_path=url,
                        mime_type="text/html",
                        page_number=1,
                    )
                    logger.info("url=%s chunks=%d", url, len(chunks))
                    if cancel_event.is_set():
                        storage.update_job_status(
                            conn,
                            job_id,
                            JobStatus.CANCELED,
                            finished_at=datetime.utcnow(),
                        )
                        return

                    texts_for_embedding = [chunk.content for chunk in chunks]
                    embeddings: list[list[float]] = []
                    if texts_for_embedding:
                        for emb in embedder.embed(texts_for_embedding):
                            if cancel_event.is_set():
                                storage.update_job_status(
                                    conn,
                                    job_id,
                                    JobStatus.CANCELED,
                                    finished_at=datetime.utcnow(),
                                )
                                return
                            embeddings.append(emb)

                    bytes_len = len(text.encode("utf-8"))
                    doc_id = upsert_document(conn, url, bytes_len, 1, source_id=source_id)
                    insert_chunks(conn, doc_id, chunks, embeddings)

                storage.update_job_status(
                    conn,
                    job_id,
                    JobStatus.SUCCEEDED,
                    finished_at=datetime.utcnow(),
                )
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("ingestion failed: %s", e)
            try:
                with psycopg.connect(db_url) as conn:
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.FAILED,
                        error=str(e),
                        finished_at=datetime.utcnow(),
                    )
            finally:
                pass
        finally:
            for h in list(logger.handlers):
                h.close()
                logger.removeHandler(h)
            _runner.clear(job_id)

    _runner.submit(job_id, _work)
    return job_id


def reindex_source(_source_id: uuid.UUID) -> uuid.UUID | None:
    """Re-ingest content for an existing source.

    The current chunks (and associated document record) for the given
    ``source_id`` are removed and a new ingestion job is started using the
    stored source parameters. The newly created job identifier is returned,
    or ``None`` if the source cannot be found or lacks the required
    parameters.
    """

    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

    with connect_and_init(db_url) as conn:

        with conn.cursor() as cur:
            cur.execute(
                "SELECT type, path, url FROM sources WHERE id = %s AND deleted_at IS NULL",
                (_source_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            type_val, path, url = row
            identifier = path or url
            if identifier:
                # Remove existing chunks/documents for this source. Deleting the
                # document record cascades to ``chunks``.
                cur.execute(
                    "DELETE FROM documents WHERE path = %s",
                    (identifier,),
                )

        conn.commit()

    source_type = SourceType(type_val)
    if source_type == SourceType.LOCAL_DIR and path:
        return ingest_local(Path(path))
    if source_type == SourceType.URL and url:
        return ingest_url(url)
    if source_type in {
        SourceType.DATABASE,
        SourceType.API,
        SourceType.AUDIO_TRANSCRIPT,
        SourceType.VIDEO_TRANSCRIPT,
    }:
        return ingest_source(source_id)
    return None


def rerun_job(_job_id: uuid.UUID) -> uuid.UUID | None:
    """Recreate a job using its original source parameters.

    Returns the new job identifier or ``None`` if the given job cannot be
    found.
    """

    db_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )

    with connect_and_init(db_url) as conn:

        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_id FROM ingestion_jobs WHERE id = %s",
                (_job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            source_id = row[0]

    return reindex_source(source_id)


def cancel_job(job_id: uuid.UUID) -> None:
    _runner.cancel(job_id)
    _runner.clear(job_id)
    logger = logging.getLogger(f"ingestion.{job_id}")
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    with psycopg.connect(db_url) as conn:
        job = storage.get_job(conn, job_id)
        if job and job.status not in {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELED,
        }:
            storage.update_job_status(
                conn,
                job_id,
                JobStatus.CANCELED,
                finished_at=datetime.utcnow(),
            )


def wait_for_job(job_id: uuid.UUID) -> None:
    """Block until the given job finishes."""
    future = _runner.get(job_id)
    if future:
        future.result()


def get_job(job_id: uuid.UUID) -> Job | None:
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    with psycopg.connect(db_url) as conn:
        return storage.get_job(conn, job_id)


def list_jobs() -> List[Job]:
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    with psycopg.connect(db_url) as conn:
        return list(storage.list_jobs(conn))


def read_job_log(job_id: uuid.UUID, offset: int = 0, limit: int = 16_384) -> JobLogSlice:
    """Read a portion of a job log.

    Parameters
    ----------
    job_id:
        Identifier of the job whose log should be read.
    offset:
        Byte offset in the log file from which to start reading.
    limit:
        Maximum number of bytes to read from the log file.
    """

    db_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    with psycopg.connect(db_url) as conn:
        job = storage.get_job(conn, job_id)

    if not job or not job.log_path:
        return JobLogSlice(
            content="", next_offset=offset, status=job.status if job else None
        )

    path = Path(job.log_path)
    if not path.exists():
        return JobLogSlice(content="", next_offset=offset, status=job.status)

    with path.open("rb") as f:
        f.seek(offset)
        data = f.read(limit)
    content = data.decode("utf-8", errors="ignore")
    next_offset = offset + len(data)

    status = (
        job.status
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
        else None
    )
    return JobLogSlice(content=content, next_offset=next_offset, status=status)
