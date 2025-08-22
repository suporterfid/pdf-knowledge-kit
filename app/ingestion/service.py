"""High level ingestion service and helpers."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, List
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from fastembed import TextEmbedding
from pdf2image import convert_from_path
from pypdf import PdfReader
import pytesseract
import psycopg
from pgvector.psycopg import register_vector

from . import storage
from .models import Job, JobLogSlice, JobStatus, SourceType
from .runner import IngestionRunner

# Multilingual embedding model
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"

# ---------------------------------------------------------------------------
# Helper functions moved from the legacy ``ingest.py`` script
# ---------------------------------------------------------------------------

def read_md_text(md_path: Path) -> str:
    """Read a Markdown file as UTF-8 text."""
    try:
        with md_path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:  # pragma: no cover - defensive
        print(f"[WARN] Falha ao ler {md_path}: {e}")
        return ""


def read_pdf_text(pdf_path: Path, use_ocr: bool = False, ocr_lang: str | None = None) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        pages_text = []
        for p in reader.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            pages_text.append(t)

        if any(t.strip() for t in pages_text):
            return "\n".join(pages_text)

        if use_ocr:
            try:
                ocr_lang = ocr_lang or os.getenv("OCR_LANG") or "eng+por+spa"
                available_langs = set(pytesseract.get_languages(config=""))
                requested_langs = {lang.strip() for lang in ocr_lang.split("+") if lang.strip()}
                missing_langs = requested_langs - available_langs
                if missing_langs:
                    print(f"[WARN] Missing OCR language(s): {', '.join(sorted(missing_langs))}")

                images = convert_from_path(str(pdf_path))
                ocr_texts = []
                for img in images:
                    try:
                        txt = pytesseract.image_to_string(img, lang=ocr_lang)
                    except Exception:
                        txt = ""
                    ocr_texts.append(txt)
                return "\n".join(ocr_texts)
            except Exception as e:
                print(f"[WARN] Falha no OCR para {pdf_path}: {e}")
                return ""
        return ""
    except Exception as e:
        print(f"[WARN] Falha ao ler {pdf_path}: {e}")
        return ""


def read_url_text(url: str) -> str:
    """Fetch a URL and return readable text content."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return " ".join(soup.stripped_strings)
    except Exception as e:
        print(f"[WARN] Falha ao ler URL {url}: {e}")
        return ""


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> List[str]:
    if not text:
        return []
    text = text.replace("\r", "")
    parts = text.split("\n\n")
    chunks: List[str] = []
    buf = ""
    for part in parts:
        if len(buf) + len(part) + 2 <= max_chars:
            buf += (("\n\n" if buf else "") + part)
        else:
            if buf:
                chunks.append(buf.strip())
            buf = part
            while len(buf) > max_chars:
                chunks.append(buf[:max_chars].strip())
                buf = buf[max_chars - overlap:]
    if buf:
        chunks.append(buf.strip())

    out: List[str] = []
    for i, ch in enumerate(chunks):
        if i == 0:
            out.append(ch)
        else:
            prev = out[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            merged = (tail + "\n\n" + ch).strip() if tail else ch
            out.append(merged if len(merged) <= max_chars + overlap else ch)
    return out


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


def upsert_document(conn: psycopg.Connection, path: str | Path, bytes_len: int, page_count: int) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE path = %s", (str(path),))
        row = cur.fetchone()
        if row:
            return row[0]

        doc_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO documents (id, path, bytes, page_count, created_at) VALUES (%s, %s, %s, %s, now())",
            (doc_id, str(path), bytes_len, page_count),
        )
        conn.commit()
        return doc_id


def insert_chunks(conn: psycopg.Connection, doc_id: uuid.UUID, chunks: Iterable[str], embeddings: Iterable[list[float]]) -> None:
    with conn.cursor() as cur:
        for i, (ch, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                "INSERT INTO chunks (doc_id, chunk_index, content, token_est, embedding) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (doc_id, chunk_index) DO NOTHING",
                (doc_id, i, ch, int(len(ch) / 4), emb),
            )
    conn.commit()

# ---------------------------------------------------------------------------
# High level service API
# ---------------------------------------------------------------------------

_runner = IngestionRunner()


def _setup_job_logging(job_id: uuid.UUID) -> tuple[logging.Logger, Path]:
    log_dir = Path("logs/jobs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job_id}.log"
    logger = logging.getLogger(f"ingestion.{job_id}")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    logger.addHandler(fh)
    return logger, log_path


def ingest_local(path: Path, *, use_ocr: bool = False, ocr_lang: str | None = None) -> uuid.UUID:
    """Ingest a local Markdown or PDF file."""

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

                suffix = path.suffix.lower()
                if suffix == ".pdf":
                    text = read_pdf_text(path, use_ocr=use_ocr, ocr_lang=ocr_lang)
                    page_count = len(PdfReader(str(path)).pages)
                elif suffix == ".md":
                    text = read_md_text(path)
                    page_count = 1
                else:
                    text = ""
                    page_count = 1

                if cancel_event.is_set():
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.CANCELED,
                        finished_at=datetime.utcnow(),
                    )
                    return

                chunks = chunk_text(text)
                logger.info("chunks=%d", len(chunks))
                if cancel_event.is_set():
                    storage.update_job_status(
                        conn,
                        job_id,
                        JobStatus.CANCELED,
                        finished_at=datetime.utcnow(),
                    )
                    return

                embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
                embeddings: list[list[float]] = []
                for emb in embedder.embed(chunks):
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
                doc_id = upsert_document(conn, path, bytes_len, page_count)
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

                embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

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

                    chunks = chunk_text(text)
                    logger.info("url=%s chunks=%d", url, len(chunks))
                    if cancel_event.is_set():
                        storage.update_job_status(
                            conn,
                            job_id,
                            JobStatus.CANCELED,
                            finished_at=datetime.utcnow(),
                        )
                        return

                    embeddings: list[list[float]] = []
                    for emb in embedder.embed(chunks):
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
                    doc_id = upsert_document(conn, url, bytes_len, 1)
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
