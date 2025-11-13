"""Test Row Level Security (RLS) tenant isolation for documents and chunks.

This module verifies that RLS policies correctly enforce tenant isolation by:
1. Creating documents and chunks for different tenants
2. Verifying that queries filtered by app.tenant_id only return data for that tenant
3. Ensuring that without tenant_id set, all data is visible (backward compatibility)
"""

import os
from uuid import uuid4

import psycopg
import pytest
from pgvector.psycopg import register_vector


def _get_conn():
    """Get a database connection or skip the test if unavailable."""
    url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    try:
        conn = psycopg.connect(url)
    except Exception:
        pytest.skip("database not available")
    register_vector(conn)
    return conn


def _setup_test_schema(conn):
    """Set up test tables with RLS policies."""
    with conn.cursor() as cur:
        # Create test organizations table if it doesn't exist
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL,
                subdomain TEXT NOT NULL UNIQUE,
                plan_type TEXT NOT NULL DEFAULT 'free'
            )
        """
        )

        # Create test documents table with organization_id
        cur.execute("DROP TABLE IF EXISTS test_chunks CASCADE")
        cur.execute("DROP TABLE IF EXISTS test_documents CASCADE")

        cur.execute(
            """
            CREATE TABLE test_documents (
                id UUID PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE test_chunks (
                id BIGSERIAL PRIMARY KEY,
                doc_id UUID NOT NULL REFERENCES test_documents(id) ON DELETE CASCADE,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR(3),
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
                UNIQUE (doc_id, chunk_index)
            )
        """
        )

        # Enable RLS on both tables
        cur.execute("ALTER TABLE test_documents ENABLE ROW LEVEL SECURITY")
        cur.execute("ALTER TABLE test_chunks ENABLE ROW LEVEL SECURITY")

        # Create RLS policies
        cur.execute(
            """
            CREATE POLICY test_documents_tenant_isolation ON test_documents
                FOR ALL
                USING (
                    organization_id::text = current_setting('app.tenant_id', true)
                    OR current_setting('app.tenant_id', true) IS NULL
                    OR current_setting('app.tenant_id', true) = ''
                )
        """
        )

        cur.execute(
            """
            CREATE POLICY test_chunks_tenant_isolation ON test_chunks
                FOR ALL
                USING (
                    organization_id::text = current_setting('app.tenant_id', true)
                    OR current_setting('app.tenant_id', true) IS NULL
                    OR current_setting('app.tenant_id', true) = ''
                )
        """
        )
    conn.commit()


def _cleanup_test_schema(conn):
    """Clean up test tables."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS test_chunks CASCADE")
        cur.execute("DROP TABLE IF EXISTS test_documents CASCADE")
        cur.execute("DROP TABLE IF EXISTS organizations CASCADE")
    conn.commit()


def test_rls_filters_documents_by_tenant():
    """Test that RLS policies filter documents by tenant_id."""
    conn = _get_conn()
    _setup_test_schema(conn)

    # Create two organizations
    org1_id = uuid4()
    org2_id = uuid4()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organizations (id, name, subdomain) VALUES (%s, %s, %s)",
            (org1_id, "Org1", "org1"),
        )
        cur.execute(
            "INSERT INTO organizations (id, name, subdomain) VALUES (%s, %s, %s)",
            (org2_id, "Org2", "org2"),
        )

        # Create documents for each organization
        doc1_id = uuid4()
        doc2_id = uuid4()
        cur.execute(
            "INSERT INTO test_documents (id, path, organization_id) VALUES (%s, %s, %s)",
            (doc1_id, "doc1.pdf", org1_id),
        )
        cur.execute(
            "INSERT INTO test_documents (id, path, organization_id) VALUES (%s, %s, %s)",
            (doc2_id, "doc2.pdf", org2_id),
        )

        # Create chunks for each document
        cur.execute(
            "INSERT INTO test_chunks (doc_id, chunk_index, content, embedding, organization_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (doc1_id, 0, "chunk from org1", [1, 0, 0], org1_id),
        )
        cur.execute(
            "INSERT INTO test_chunks (doc_id, chunk_index, content, embedding, organization_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (doc2_id, 0, "chunk from org2", [0, 1, 0], org2_id),
        )
    conn.commit()

    # Test 1: Query with tenant_id set to org1
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(org1_id),))
        cur.execute("SELECT path FROM test_documents")
        docs = cur.fetchall()
        assert len(docs) == 1
        assert docs[0][0] == "doc1.pdf"

        cur.execute("SELECT content FROM test_chunks")
        chunks = cur.fetchall()
        assert len(chunks) == 1
        assert chunks[0][0] == "chunk from org1"

    # Test 2: Query with tenant_id set to org2
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(org2_id),))
        cur.execute("SELECT path FROM test_documents")
        docs = cur.fetchall()
        assert len(docs) == 1
        assert docs[0][0] == "doc2.pdf"

        cur.execute("SELECT content FROM test_chunks")
        chunks = cur.fetchall()
        assert len(chunks) == 1
        assert chunks[0][0] == "chunk from org2"

    # Test 3: Query without tenant_id (backward compatibility - should see all)
    with conn.cursor() as cur:
        cur.execute("RESET app.tenant_id")
        cur.execute("SELECT path FROM test_documents ORDER BY path")
        docs = cur.fetchall()
        assert len(docs) == 2
        assert docs[0][0] == "doc1.pdf"
        assert docs[1][0] == "doc2.pdf"

        cur.execute("SELECT content FROM test_chunks ORDER BY content")
        chunks = cur.fetchall()
        assert len(chunks) == 2

    _cleanup_test_schema(conn)
    conn.close()


def test_rls_prevents_cross_tenant_access():
    """Test that queries with one tenant_id cannot access another tenant's data."""
    conn = _get_conn()
    _setup_test_schema(conn)

    # Create two organizations
    org1_id = uuid4()
    org2_id = uuid4()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organizations (id, name, subdomain) VALUES (%s, %s, %s)",
            (org1_id, "Org1", "org1"),
        )
        cur.execute(
            "INSERT INTO organizations (id, name, subdomain) VALUES (%s, %s, %s)",
            (org2_id, "Org2", "org2"),
        )

        # Create a document for org1
        doc_id = uuid4()
        cur.execute(
            "INSERT INTO test_documents (id, path, organization_id) VALUES (%s, %s, %s)",
            (doc_id, "secret_doc.pdf", org1_id),
        )
        cur.execute(
            "INSERT INTO test_chunks (doc_id, chunk_index, content, embedding, organization_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (doc_id, 0, "secret content", [1, 0, 0], org1_id),
        )
    conn.commit()

    # Try to access org1's document while set as org2
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(org2_id),))
        cur.execute(
            "SELECT path FROM test_documents WHERE path = %s", ("secret_doc.pdf",)
        )
        docs = cur.fetchall()
        assert (
            len(docs) == 0
        ), "Should not be able to see org1's document when tenant_id is org2"

        cur.execute(
            "SELECT content FROM test_chunks WHERE content LIKE %s", ("%secret%",)
        )
        chunks = cur.fetchall()
        assert (
            len(chunks) == 0
        ), "Should not be able to see org1's chunks when tenant_id is org2"

    _cleanup_test_schema(conn)
    conn.close()


def test_rls_with_join_query():
    """Test that RLS works correctly with JOIN queries (like the RAG query)."""
    conn = _get_conn()
    _setup_test_schema(conn)

    # Create two organizations
    org1_id = uuid4()
    org2_id = uuid4()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organizations (id, name, subdomain) VALUES (%s, %s, %s)",
            (org1_id, "Org1", "org1"),
        )
        cur.execute(
            "INSERT INTO organizations (id, name, subdomain) VALUES (%s, %s, %s)",
            (org2_id, "Org2", "org2"),
        )

        # Create documents and chunks for both orgs
        doc1_id = uuid4()
        doc2_id = uuid4()
        cur.execute(
            "INSERT INTO test_documents (id, path, organization_id) VALUES (%s, %s, %s)",
            (doc1_id, "org1_doc.pdf", org1_id),
        )
        cur.execute(
            "INSERT INTO test_documents (id, path, organization_id) VALUES (%s, %s, %s)",
            (doc2_id, "org2_doc.pdf", org2_id),
        )
        cur.execute(
            "INSERT INTO test_chunks (doc_id, chunk_index, content, embedding, organization_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (doc1_id, 0, "org1 chunk", [1, 0, 0], org1_id),
        )
        cur.execute(
            "INSERT INTO test_chunks (doc_id, chunk_index, content, embedding, organization_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (doc2_id, 0, "org2 chunk", [0, 1, 0], org2_id),
        )
    conn.commit()

    # Query with JOIN (similar to RAG query) for org1
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(org1_id),))
        cur.execute(
            """
            SELECT d.path, c.chunk_index, c.content
            FROM test_chunks c
            JOIN test_documents d ON d.id = c.doc_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.chunk_index
        """
        )
        results = cur.fetchall()
        assert len(results) == 1
        assert results[0][0] == "org1_doc.pdf"
        assert results[0][2] == "org1 chunk"

    # Query with JOIN for org2
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(org2_id),))
        cur.execute(
            """
            SELECT d.path, c.chunk_index, c.content
            FROM test_chunks c
            JOIN test_documents d ON d.id = c.doc_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.chunk_index
        """
        )
        results = cur.fetchall()
        assert len(results) == 1
        assert results[0][0] == "org2_doc.pdf"
        assert results[0][2] == "org2 chunk"

    _cleanup_test_schema(conn)
    conn.close()
