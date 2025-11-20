import os
from uuid import uuid4

import psycopg
import pytest
from app import rag
from pgvector.psycopg import register_vector

TEST_TENANT = "tenant-a"


# Helper to get a database connection or skip the test if unavailable


def _set_tenant(conn: psycopg.Connection, tenant_id: str | None) -> None:
    if tenant_id is None:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', NULL, false)")
        return
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))


def _get_conn(*, tenant_id: str | None = None):
    url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    try:
        conn = psycopg.connect(url)
    except Exception:
        pytest.skip("database not available")
    try:
        register_vector(conn)
    except Exception:
        pass
    if tenant_id is not None:
        _set_tenant(conn, tenant_id)
    return conn


def _setup_db(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("DROP TABLE IF EXISTS documents")
        cur.execute(
            "CREATE TABLE documents (id UUID PRIMARY KEY, tenant_id TEXT NOT NULL, path TEXT NOT NULL)"
        )
        cur.execute(
            """
            CREATE TABLE chunks (
                id BIGSERIAL PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR(3)
            )
            """
        )
        )
    conn.commit()
    register_vector(conn)


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
        cur.execute(
            "INSERT INTO documents (id, tenant_id, path) VALUES (%s, %s, %s)",
            (doc1, TEST_TENANT, "doc1"),
        )
        cur.execute(
            "INSERT INTO documents (id, tenant_id, path) VALUES (%s, %s, %s)",
            (doc2, TEST_TENANT, "doc2"),
        )
        cur.execute(
            "INSERT INTO chunks (tenant_id, doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s)",
            (TEST_TENANT, doc1, 0, "chunk1", [1, 0, 0]),
        )
        cur.execute(
            "INSERT INTO chunks (tenant_id, doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s)",
            (TEST_TENANT, doc2, 0, "chunk2", [0, 1, 0]),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(rag, "embedder", DummyEmbedder([1, 0, 0]))

    def _tenant_conn(*, tenant_id: str | None = None):
        effective = tenant_id or TEST_TENANT
        return _get_conn(tenant_id=effective)

    monkeypatch.setattr(rag, "get_conn", _tenant_conn)

    context, sources = rag.build_context("q", 2, tenant_id=TEST_TENANT)
    assert context == "chunk1\n\nchunk2"
    assert [s["path"] for s in sources] == ["doc1", "doc2"]

    cleanup = _get_conn()
    with cleanup.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("DROP TABLE IF EXISTS documents")
    cleanup.commit()
    cleanup.close()


def test_build_context_filters_out_other_tenants(monkeypatch):
    conn = _get_conn()
    _setup_db(conn)
    local_tenant = TEST_TENANT
    other_tenant = "tenant-b"
    doc_local, doc_other = uuid4(), uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (id, tenant_id, path) VALUES (%s, %s, %s)",
            (doc_local, local_tenant, "local"),
        )
        cur.execute(
            "INSERT INTO documents (id, tenant_id, path) VALUES (%s, %s, %s)",
            (doc_other, other_tenant, "other"),
        )
        cur.execute(
            "INSERT INTO chunks (tenant_id, doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s)",
            (local_tenant, doc_local, 0, "chunk-local", [1, 0, 0]),
        )
        cur.execute(
            "INSERT INTO chunks (tenant_id, doc_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s)",
            (other_tenant, doc_other, 0, "chunk-other", [1, 0, 0]),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(rag, "embedder", DummyEmbedder([1, 0, 0]))

    def _tenant_conn(*, tenant_id: str | None = None):
        effective = tenant_id or local_tenant
        return _get_conn(tenant_id=effective)

    monkeypatch.setattr(rag, "get_conn", _tenant_conn)

    context, sources = rag.build_context("q", 2, tenant_id=local_tenant)
    assert "chunk-other" not in context
    assert all(src["path"] != "other" for src in sources)

    other_context, other_sources = rag.build_context("q", 2, tenant_id=other_tenant)
    assert "chunk-local" not in other_context
    assert all(src["path"] != "local" for src in other_sources)

    cleanup = _get_conn()
    with cleanup.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("DROP TABLE IF EXISTS documents")
    cleanup.commit()
    cleanup.close()
