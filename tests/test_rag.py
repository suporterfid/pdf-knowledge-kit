import os
from uuid import uuid4

import psycopg
import pytest
from pgvector.psycopg import register_vector

from app import rag


# Helper to get a database connection or skip the test if unavailable

def _get_conn():
    url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    try:
        conn = psycopg.connect(url)
    except Exception:
        pytest.skip("database not available")
    register_vector(conn)
    return conn


def _setup_db(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("DROP TABLE IF EXISTS documents")
        cur.execute("CREATE TABLE documents (id UUID PRIMARY KEY, path TEXT NOT NULL)")
        cur.execute(
            """
            CREATE TABLE chunks (
                id BIGSERIAL PRIMARY KEY,
                doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR(3)
            )
            """
        )
    conn.commit()


class DummyEmbedder:
    def __init__(self, vec):
        self.vec = vec

    def embed(self, texts):
        return [self.vec]


def test_build_context_returns_expected_sources(monkeypatch):
    conn = _get_conn()
    _setup_db(conn)
    doc1, doc2 = uuid4(), uuid4()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO documents (id, path) VALUES (%s, %s)", (doc1, "doc1"))
        cur.execute("INSERT INTO documents (id, path) VALUES (%s, %s)", (doc2, "doc2"))
        cur.execute(
            "INSERT INTO chunks (doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s)",
            (doc1, 0, "chunk1", [1, 0, 0]),
        )
        cur.execute(
            "INSERT INTO chunks (doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s)",
            (doc2, 0, "chunk2", [0, 1, 0]),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(rag, "embedder", DummyEmbedder([1, 0, 0]))
    monkeypatch.setattr(rag, "get_conn", _get_conn)

    context, sources = rag.build_context("q", 2)
    assert context == "chunk1\n\nchunk2"
    assert [s["path"] for s in sources] == ["doc1", "doc2"]

    cleanup = _get_conn()
    with cleanup.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("DROP TABLE IF EXISTS documents")
    cleanup.commit()
    cleanup.close()
