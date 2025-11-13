"""RAG retrieval helpers (vector search + lexical reranking).

This module encapsulates the retrieval side of the RAG pipeline used by the
FastAPI backend:

- Creates a ``TextEmbedding`` instance for multilingual sentence embeddings.
- Opens PostgreSQL connections with pgvector support registered.
- Retrieves the most similar chunks by vector distance.
- Applies an optional lightweight lexical reranker (BM25) over the candidates
  to improve the final top-k ordering for short, keyworded queries.

Returned values include a plain-text context (to be fed to an LLM) and the
structured list of sources for transparency and UI display.
"""

import os
import psycopg
from pgvector.psycopg import register_vector
from fastembed import TextEmbedding
# Attempt to register a CLS-pooled variant when supported by the installed
# fastembed version. When unsupported, this import is a no-op and we fall back
# to the base mean-pooled model (see embedder creation below).
import embedding  # attempts to register custom CLS-pooled model (no-op if unsupported)
from typing import Iterable

try:
    # Lightweight lexical reranker
    from rank_bm25 import BM25Okapi  # type: ignore
except Exception:  # pragma: no cover - optional dep
    BM25Okapi = None  # type: ignore
from typing import List, Tuple, Dict

# Prefer a CLS-pooled custom model if available; otherwise, fall back to the
# widely used mean-pooled base model from Sentence-Transformers. The fallback
# ensures the app boots even when fastembed doesn't support custom models.
try:
    embedder = TextEmbedding(model_name="paraphrase-multilingual-MiniLM-L12-v2-cls")
except Exception:
    embedder = TextEmbedding(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )


def get_conn() -> psycopg.Connection:
    """Open a PostgreSQL connection and register pgvector type adapters.

    Connection parameters are read from environment variables (compatible with
    Docker Compose defaults). The caller is responsible for closing the
    returned connection.
    """
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
    """Very small tokenizer for BM25: lowercase and keep only alpha-numerics."""
    return [
        t.lower()
        for t in ''.join(c if c.isalnum() else ' ' for c in text).split()
        if t
    ]


def _bm25_rerank(query: str, sources: List[Dict]) -> List[Dict]:
    """Apply BM25 lexical reranking over vector-retrieved candidates.

    If the optional dependency ``rank-bm25`` isn't installed, this becomes a
    no-op and the original order is preserved.
    """
    if not BM25Okapi or not sources:
        return sources
    corpus = [src.get("content") or "" for src in sources]
    tokenized_corpus = [_tokenize(c) for c in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(scores, sources), key=lambda x: x[0], reverse=True)
    return [s for _, s in ranked]


def build_context(question: str, k: int) -> Tuple[str, List[Dict]]:
    """Retrieve top-k chunks and build a context string for the LLM.

    Steps
    -----
    1. Embed the raw question using the configured sentence embedder.
    2. Query pgvector by L2 distance operator ``<->`` to get the most similar
       chunks. We intentionally retrieve more than ``k`` results (``pre_k``)
       to give the reranker headroom to improve ordering.
    3. Optionally apply BM25 reranking (if available) and select the final
       top-``k`` chunks.
    4. Concatenate selected chunks into a single context string (double new
       lines between chunks) and return it along with the structured sources.

    Parameters
    ----------
    question:
        User question to retrieve supporting context for.
    k:
        Number of final chunks to return after reranking.

    Returns
    -------
    context:
        Plain-text context to pass to the LLM.
    sources:
        List of dictionaries containing path, chunk index, content and raw
        vector distance for UI display and auditing.
    """
    conn = get_conn()
    # 1) Embed the raw question (no "query:" prefix needed with this model family)
    qvec = list(embedder.embed([question]))[0]
    # 2) Retrieve a larger candidate set for reranking. ``<->`` is pgvector's
    # L2 (Euclidean) distance operator. We choose pre_k = max(k*4, 20)
    # heuristically to balance quality and latency.
    pre_k = max(k * 4, 20)
    # Note: Row Level Security (RLS) policies automatically filter chunks and documents
    # by organization_id based on the app.tenant_id session variable set by the
    # TenantContextMiddleware. No explicit WHERE clause for tenant filtering is needed.
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
    # 3) Rerank lexically and select top-k
    ranked = _bm25_rerank(question, candidates)[:k]
    # 4) Build context
    context = "\n\n".join(src["content"] for src in ranked)
    return context, ranked
