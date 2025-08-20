"""High level ingestion service and helpers."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from bs4 import BeautifulSoup
from fastembed import TextEmbedding
from pdf2image import convert_from_path
from pypdf import PdfReader
import pytesseract
import psycopg
from pgvector.psycopg import register_vector

from .models import IngestionJob, IngestionJobStatus
from .runner import IngestionRunner

# Multilingual embedding model
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

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


def ensure_schema(conn: psycopg.Connection, schema_sql_path: Path) -> None:
    with conn.cursor() as cur:
        cur.execute(open(schema_sql_path, "r", encoding="utf-8").read())
    conn.commit()


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
_jobs: Dict[uuid.UUID, IngestionJob] = {}
_job_logs: Dict[uuid.UUID, Path] = {}


def _setup_job_logging(job_id: uuid.UUID) -> logging.Logger:
    log_dir = Path("logs/jobs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job_id}.log"
    logger = logging.getLogger(f"ingestion.{job_id}")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    logger.addHandler(fh)
    _job_logs[job_id] = log_path
    return logger


def ingest_local(path: Path, *, use_ocr: bool = False, ocr_lang: str | None = None) -> uuid.UUID:
    job_id = uuid.uuid4()
    logger = _setup_job_logging(job_id)
    job = IngestionJob(
        id=job_id,
        source_id=uuid.uuid4(),
        status=IngestionJobStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    _jobs[job_id] = job

    def _work(cancel_event):
        job.status = IngestionJobStatus.RUNNING
        try:
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                text = read_pdf_text(path, use_ocr=use_ocr, ocr_lang=ocr_lang)
            elif suffix == ".md":
                text = read_md_text(path)
            else:
                text = ""
            if cancel_event.is_set():
                job.status = IngestionJobStatus.CANCELED
                return
            chunks = chunk_text(text)
            logger.info("chunks=%d", len(chunks))
            if cancel_event.is_set():
                job.status = IngestionJobStatus.CANCELED
                return
            job.status = IngestionJobStatus.COMPLETED
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("ingestion failed: %s", e)
            job.status = IngestionJobStatus.FAILED
            job.error = str(e)
        finally:
            for h in list(logger.handlers):
                h.close()
                logger.removeHandler(h)

    _runner.submit(job_id, _work)
    return job_id


def ingest_url(url: str) -> uuid.UUID:
    return ingest_urls([url])


def ingest_urls(urls: List[str]) -> uuid.UUID:
    job_id = uuid.uuid4()
    logger = _setup_job_logging(job_id)
    job = IngestionJob(
        id=job_id,
        source_id=uuid.uuid4(),
        status=IngestionJobStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    _jobs[job_id] = job

    def _work(cancel_event):
        job.status = IngestionJobStatus.RUNNING
        try:
            for url in urls:
                if cancel_event.is_set():
                    job.status = IngestionJobStatus.CANCELED
                    return
                text = read_url_text(url)
                if cancel_event.is_set():
                    job.status = IngestionJobStatus.CANCELED
                    return
                chunks = chunk_text(text)
                logger.info("url=%s chunks=%d", url, len(chunks))
                if cancel_event.is_set():
                    job.status = IngestionJobStatus.CANCELED
                    return
            job.status = IngestionJobStatus.COMPLETED
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("ingestion failed: %s", e)
            job.status = IngestionJobStatus.FAILED
            job.error = str(e)
        finally:
            for h in list(logger.handlers):
                h.close()
                logger.removeHandler(h)

    _runner.submit(job_id, _work)
    return job_id


def reindex_source(_source_id: uuid.UUID) -> None:
    """Placeholder for vector index recreation."""
    return None


def cancel_job(job_id: uuid.UUID) -> None:
    _runner.cancel(job_id)
    job = _jobs.get(job_id)
    if job and job.status not in {IngestionJobStatus.COMPLETED, IngestionJobStatus.FAILED}:
        job.status = IngestionJobStatus.CANCELED


def get_job(job_id: uuid.UUID) -> IngestionJob | None:
    return _jobs.get(job_id)


def list_jobs() -> List[IngestionJob]:
    return list(_jobs.values())


def read_job_log(job_id: uuid.UUID) -> str:
    path = _job_logs.get(job_id)
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return ""
