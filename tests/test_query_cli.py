import os
import sys
from uuid import uuid4

import psycopg
import pytest
import query
from pgvector.psycopg import register_vector


def _get_conn():
    url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
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
    def embed(self, texts):
        return [[1, 0, 0]]


def test_query_cli(monkeypatch, capsys):
    conn = _get_conn()
    _setup_db(conn)
    doc = uuid4()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO documents (id, path) VALUES (%s, %s)", (doc, "doc1"))
        cur.execute(
            "INSERT INTO chunks (doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s)",
            (doc, 0, "chunk1", [1, 0, 0]),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(query, "TextEmbedding", lambda model_name: DummyEmbedder())
    monkeypatch.setattr(query.psycopg, "connect", lambda dsn: _get_conn())
    monkeypatch.setattr(sys, "argv", ["query.py", "--q", "hello", "--k", "1"])

    query.main()
    output = capsys.readouterr().out
    assert "[1] doc1  #chunk 0" in output

    cleanup = _get_conn()
    with cleanup.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("DROP TABLE IF EXISTS documents")
    cleanup.commit()
    cleanup.close()
