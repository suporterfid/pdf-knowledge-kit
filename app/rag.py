import os
import psycopg
from pgvector.psycopg import register_vector
from fastembed import TextEmbedding
from typing import List, Tuple, Dict

# Use a supported multilingual embedding model
embedder = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def get_conn():
    dsn = (
        f"host={os.getenv('PGHOST','localhost')} "
        f"port={os.getenv('PGPORT','5432')} "
        f"dbname={os.getenv('PGDATABASE','pdfkb')} "
        f"user={os.getenv('PGUSER','pdfkb')} "
        f"password={os.getenv('PGPASSWORD','pdfkb')}"
    )
    conn = psycopg.connect(dsn)
    register_vector(conn)
    return conn


def build_context(question: str, k: int) -> Tuple[str, List[Dict]]:
    """Retrieve top-k chunks relevant to the question and build a text context."""
    conn = get_conn()
    qvec = list(embedder.embed([f"query: {question}"]))[0]
    sql = """
    SELECT d.path, c.chunk_index, c.content, (c.embedding <-> %s) AS distance
    FROM chunks c
    JOIN documents d ON d.id = c.doc_id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <-> %s
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (qvec, qvec, k))
        rows = cur.fetchall()
    conn.close()
    sources = [
        {
            "path": path,
            "chunk_index": idx,
            "content": content,
            "distance": dist,
        }
        for path, idx, content, dist in rows
    ]
    context = "\n\n".join(src["content"] for src in sources)
    return context, sources
