import os
import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
from tqdm import tqdm

# Embeddings (multilíngue PT/EN)
from fastembed import TextEmbedding


def read_md_text(md_path: Path) -> str:
    try:
        return md_path.read_text(encoding="utf-8")
    except Exception as e:
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
                    print(
                        f"[WARN] Missing OCR language(s): {', '.join(sorted(missing_langs))}"
                    )

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

def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200):
    """
    Simples chunk por caracteres, preservando quebras.
    max_chars ~300-400 tokens, com overlap para contexto.
    """
    if not text:
        return []
    text = text.replace("\r", "")
    parts = text.split("\n\n")
    chunks = []
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

    # Ajusta com overlap final
    out = []
    for i, ch in enumerate(chunks):
        if i == 0:
            out.append(ch)
        else:
            prev = out[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            merged = (tail + "\n\n" + ch).strip() if tail else ch
            out.append(merged if len(merged) <= max_chars + overlap else ch)
    return out

def ensure_schema(conn: psycopg.Connection, schema_sql_path: Path):
    with conn.cursor() as cur:
        cur.execute(open(schema_sql_path, "r", encoding="utf-8").read())
    conn.commit()

def upsert_document(conn: psycopg.Connection, path: Path, bytes_len: int, page_count: int) -> uuid.UUID:
    with conn.cursor() as cur:
        # Existe?
        cur.execute("SELECT id FROM documents WHERE path = %s", (str(path),))
        row = cur.fetchone()
        if row:
            return row[0]

        doc_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO documents (id, path, bytes, page_count, created_at) VALUES (%s, %s, %s, %s, now())",
            (doc_id, str(path), bytes_len, page_count)
        )
        conn.commit()
        return doc_id

def insert_chunks(conn: psycopg.Connection, doc_id: uuid.UUID, chunks, embeddings):
    with conn.cursor() as cur:
        for i, (ch, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                "INSERT INTO chunks (doc_id, chunk_index, content, token_est, embedding) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (doc_id, chunk_index) DO NOTHING",
                (doc_id, i, ch, int(len(ch) / 4), emb)  # token_est ~ aprox.
            )
    conn.commit()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ingestão de PDFs e Markdown para Postgres+pgvector")
    parser.add_argument("--docs", type=str, default=os.getenv("DOCS_DIR", "./docs"), help="Pasta com PDFs/MD")
    parser.add_argument("--batch", type=int, default=64, help="Tamanho do batch para embeddings")
    parser.add_argument("--reindex", action="store_true", help="Recria índice vetorial após ingestão")
    parser.add_argument("--ocr", action="store_true", help="Habilita OCR para PDFs escaneados")
    parser.add_argument("--ocr-lang", type=str, help="Idiomas do Tesseract (ex.: 'eng+por'; padrão: 'eng+por+spa')")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        env_ocr = os.getenv("ENABLE_OCR")
        if env_ocr is not None:
            args.ocr = env_ocr.lower() not in ("0", "false", "no")

    dsn = f"host={os.getenv('PGHOST','db')} port={os.getenv('PGPORT','5432')} dbname={os.getenv('PGDATABASE','pdfkb')} user={os.getenv('PGUSER','pdfkb')} password={os.getenv('PGPASSWORD','pdfkb')}"
    conn = psycopg.connect(dsn)
    ensure_schema(conn, Path(__file__).with_name("schema.sql"))
    register_vector(conn)

    docs_dir = Path(args.docs)
    doc_files = sorted(list(docs_dir.rglob("*.pdf")) + list(docs_dir.rglob("*.md")))
    if not doc_files:
        print(f"[INFO] Nenhum PDF ou Markdown encontrado em {docs_dir.resolve()}")
        return

    # Use a supported multilingual embedding model
    embedder = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    for doc_path in tqdm(doc_files, desc="Processando documentos"):
        try:
            suffix = doc_path.suffix.lower()
            if suffix == ".pdf":
                text = read_pdf_text(doc_path, use_ocr=args.ocr, ocr_lang=args.ocr_lang)
            elif suffix == ".md":
                text = read_md_text(doc_path)
            else:
                continue
            if not text.strip():
                print(f"[WARN] Sem texto extraído: {doc_path}")
                continue

            chunks = chunk_text(text, max_chars=1200, overlap=200)
            if not chunks:
                print(f"[WARN] Sem chunks gerados: {doc_path}")
                continue

            bytes_len = os.path.getsize(doc_path)
            if suffix == ".pdf":
                try:
                    page_count = len(PdfReader(str(doc_path)).pages)
                except Exception:
                    page_count = 0
            else:
                page_count = 1

            doc_id = upsert_document(conn, doc_path, bytes_len, page_count)

            passages = [f"passage: {c}" for c in chunks]

            embeddings = list(embedder.embed(passages, batch_size=args.batch))

            insert_chunks(conn, doc_id, chunks, embeddings)
        except Exception as e:
            print(f"[ERROR] {doc_path}: {e}")

    if args.reindex:
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100)")
            cur.execute("ANALYZE chunks")
        conn.commit()
        print("[INFO] Índice vetorial criado/atualizado.")

    conn.close()
    print("[DONE] Ingestão finalizada.")

if __name__ == "__main__":
    main()
