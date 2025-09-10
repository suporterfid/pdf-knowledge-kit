import os
import psycopg
from pgvector.psycopg import register_vector
from fastembed import TextEmbedding
import embedding  # attempts to register custom CLS-pooled model (no-op if unsupported)
from typing import Iterable

try:
    # Lightweight lexical reranker
    from rank_bm25 import BM25Okapi  # type: ignore
except Exception:  # pragma: no cover - optional dep
    BM25Okapi = None  # type: ignore
from typing import List, Tuple, Dict

# Use a supported multilingual embedding model. Fallback to base model if
# the custom CLS-pooled variant is not available in this fastembed version.
try:
    embedder = TextEmbedding(model_name="paraphrase-multilingual-MiniLM-L12-v2-cls")
except Exception:
    embedder = TextEmbedding(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )


def get_conn():
    dsn = (
        f"host={os.getenv('PGHOST','db')} "
        f"port={os.getenv('PGPORT','5432')} "
        f"dbname={os.getenv('PGDATABASE','pdfkb')} "
        f"user={os.getenv('PGUSER','pdfkb')} "
        f"password={os.getenv('PGPASSWORD','pdfkb')}"
    )
    conn = psycopg.connect(dsn)
    register_vector(conn)
    return conn


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in ''.join(c if c.isalnum() else ' ' for c in text).split() if t]


def _bm25_rerank(query: str, sources: List[Dict]) -> List[Dict]:
    if not BM25Okapi or not sources:
        return sources
    corpus = [src["content"] or "" for src in sources]
    tokenized_corpus = [_tokenize(c) for c in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(scores, sources), key=lambda x: x[0], reverse=True)
    return [s for _, s in ranked]


def build_context(question: str, k: int) -> Tuple[str, List[Dict]]:
    """Retrieve top-k chunks via vector search, then apply a lightweight reranker."""
    conn = get_conn()
    # Embed the raw question (no prefix) for current model family
    qvec = list(embedder.embed([question]))[0]
    # Retrieve a larger candidate set for reranking
    pre_k = max(k * 4, 20)
    sql = """
    SELECT d.path, c.chunk_index, c.content, (c.embedding <-> %s) AS distance
    FROM chunks c
    JOIN documents d ON d.id = c.doc_id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <-> %s
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (qvec, qvec, pre_k))
        rows = cur.fetchall()
    conn.close()
    candidates = [
        {
            "path": path,
            "chunk_index": idx,
            "content": content,
            "distance": dist,
        }
        for path, idx, content, dist in rows
    ]
    # Rerank lexically and select top-k
    ranked = _bm25_rerank(question, candidates)[:k]
    context = "\n\n".join(src["content"] for src in ranked)
    return context, ranked
