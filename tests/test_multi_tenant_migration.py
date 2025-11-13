from __future__ import annotations

import pathlib
import uuid

import psycopg
import pytest
import sqlalchemy as sa
from app.ingestion.service import SCHEMA_PATH, ensure_schema
from sqlalchemy.engine import make_url

MULTI_TENANT_TABLES = [
    ("connector_definitions", "connector_definitions_tenant_isolation"),
    ("sources", "sources_tenant_isolation"),
    ("ingestion_jobs", "ingestion_jobs_tenant_isolation"),
    ("documents", "documents_tenant_isolation"),
    ("document_versions", "document_versions_tenant_isolation"),
    ("chunks", "chunks_tenant_isolation"),
    ("feedbacks", "feedbacks_tenant_isolation"),
    ("agents", "agents_tenant_isolation"),
    ("agent_versions", "agent_versions_tenant_isolation"),
    ("agent_tests", "agent_tests_tenant_isolation"),
    ("agent_channel_configs", "agent_channel_configs_tenant_isolation"),
    ("conversations", "conversations_tenant_isolation"),
    ("conversation_participants", "conversation_participants_tenant_isolation"),
    ("conversation_messages", "conversation_messages_tenant_isolation"),
]


def _schema_without_vector(tmp_path: pathlib.Path) -> pathlib.Path:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    schema_text = schema_text.replace(
        "CREATE EXTENSION IF NOT EXISTS vector;",
        "-- vector extension skipped in tests",
    )
    schema_text = schema_text.replace("VECTOR(384)", "DOUBLE PRECISION[]")
    path = tmp_path / "schema.sql"
    path.write_text(schema_text, encoding="utf-8")
    return path


@pytest.mark.integration
def test_multi_tenant_migration_creates_tables(tmp_path: pathlib.Path) -> None:
    testing_postgresql = pytest.importorskip("testing.postgresql")
    try:
        pg = testing_postgresql.Postgresql()
    except RuntimeError as exc:
        pytest.skip(f"testing.postgresql is unavailable: {exc}")

    schema_path = _schema_without_vector(tmp_path)

    try:
        with psycopg.connect(pg.url()) as conn:
            ensure_schema(conn, schema_sql_path=schema_path)
            ensure_schema(conn, schema_sql_path=schema_path)

        engine = sa.create_engine(
            make_url(pg.url()).set(drivername="postgresql+psycopg")
        )
        try:
            with engine.connect() as connection:
                inspector = sa.inspect(connection)
                tables = inspector.get_table_names()
                assert "organizations" in tables
                assert "users" in tables

                org_columns = {
                    col["name"] for col in inspector.get_columns("organizations")
                }
                assert {"id", "name", "subdomain", "plan_type"}.issubset(org_columns)

                user_columns = {col["name"] for col in inspector.get_columns("users")}
                assert {
                    "id",
                    "organization_id",
                    "email",
                    "password_hash",
                    "name",
                }.issubset(user_columns)

                org_indexes = inspector.get_indexes("organizations")
                assert any(
                    idx["name"] == "ix_organizations_subdomain_unique"
                    and idx.get("unique")
                    and idx.get("column_names") == ["subdomain"]
                    for idx in org_indexes
                )

                user_indexes = inspector.get_indexes("users")
                assert any(
                    idx["name"] == "ix_users_email_unique"
                    and idx.get("unique")
                    and idx.get("column_names") == ["email"]
                    for idx in user_indexes
                )
                assert any(
                    idx["name"] == "ix_users_organization_id"
                    and idx.get("column_names") == ["organization_id"]
                    for idx in user_indexes
                )

                fks = inspector.get_foreign_keys("users")
                assert any(fk["referred_table"] == "organizations" for fk in fks)

                # Every multi-tenant table must expose at least one index with tenant_id
                for table_name, _ in MULTI_TENANT_TABLES:
                    if table_name not in tables:
                        continue

                    indexes = inspector.get_indexes(table_name)
                    assert any(
                        idx.get("column_names")
                        and idx["column_names"][0] == "tenant_id"
                        for idx in indexes
                    ), f"missing tenant_id index for {table_name}"
        finally:
            engine.dispose()

        with psycopg.connect(pg.url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM app_python_migrations WHERE id = %s",
                    ("004_create_multi_tenant_tables",),
                )
                assert cur.fetchone()

                # Helper function must exist and run without tenant context
                cur.execute("SELECT app.current_tenant_id()")
                (tenant_id,) = cur.fetchone()
                assert tenant_id is None

                # Function should be SECURITY DEFINER to avoid permission surprises
                cur.execute(
                    """
                    SELECT p.prosecdef
                    FROM pg_proc AS p
                    JOIN pg_namespace AS n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'app'
                      AND p.proname = 'current_tenant_id'
                    """
                )
                (is_security_definer,) = cur.fetchone()
                assert is_security_definer is True

                # Ensure RLS is enabled with matching USING / WITH CHECK policies
                for table_name, policy_name in MULTI_TENANT_TABLES:
                    cur.execute(
                        """
                        SELECT c.relrowsecurity
                        FROM pg_class AS c
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relname = %s
                        """,
                        (table_name,),
                    )
                    result = cur.fetchone()
                    if result is None:
                        continue  # table not present in this schema snapshot
                    (rls_enabled,) = result
                    assert rls_enabled is True, f"RLS not enabled for {table_name}"

                    cur.execute(
                        """
                        SELECT pol.qual, pol.with_check
                        FROM pg_policies AS pol
                        WHERE pol.schemaname = 'public'
                          AND pol.tablename = %s
                          AND pol.policyname = %s
                        """,
                        (table_name, policy_name),
                    )
                    policy_row = cur.fetchone()
                    assert (
                        policy_row is not None
                    ), f"Missing RLS policy for {table_name}"
                    qual, with_check = policy_row
                    expected = "((tenant_id = app.current_tenant_id()))"
                    assert qual == expected
                    assert with_check == expected
    finally:
        pg.stop()


@pytest.mark.integration
def test_rls_blocks_cross_tenant_queries(tmp_path: pathlib.Path) -> None:
    testing_postgresql = pytest.importorskip("testing.postgresql")
    try:
        pg = testing_postgresql.Postgresql()
    except RuntimeError as exc:
        pytest.skip(f"testing.postgresql is unavailable: {exc}")

    schema_path = _schema_without_vector(tmp_path)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    try:
        with psycopg.connect(pg.url()) as conn:
            ensure_schema(conn, schema_sql_path=schema_path)

            source_a = uuid.uuid4()
            source_b = uuid.uuid4()
            job_a = uuid.uuid4()
            job_b = uuid.uuid4()

            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO organizations (id, name, subdomain, plan_type) VALUES (%s, %s, %s, 'free')"
                    " ON CONFLICT (id) DO NOTHING",
                    (tenant_a, "Tenant A", "tenant-a"),
                )
                cur.execute(
                    "INSERT INTO organizations (id, name, subdomain, plan_type) VALUES (%s, %s, %s, 'free')"
                    " ON CONFLICT (id) DO NOTHING",
                    (tenant_b, "Tenant B", "tenant-b"),
                )
                cur.execute(
                    "INSERT INTO sources (id, tenant_id, type, created_at) VALUES (%s, %s, %s, now())",
                    (source_a, tenant_a, "url"),
                )
                cur.execute(
                    "INSERT INTO sources (id, tenant_id, type, created_at) VALUES (%s, %s, %s, now())",
                    (source_b, tenant_b, "url"),
                )
                cur.execute(
                    "INSERT INTO ingestion_jobs (id, tenant_id, source_id, status, created_at)"
                    " VALUES (%s, %s, %s, %s, now())",
                    (job_a, tenant_a, source_a, "queued"),
                )
                cur.execute(
                    "INSERT INTO ingestion_jobs (id, tenant_id, source_id, status, created_at)"
                    " VALUES (%s, %s, %s, %s, now())",
                    (job_b, tenant_b, source_b, "queued"),
                )
            conn.commit()

            with conn.cursor() as cur:
                cur.execute("SET app.tenant_id = %s", (str(tenant_a),))
                cur.execute("SELECT COUNT(*) FROM sources")
                assert cur.fetchone() == (1,)
                cur.execute("SELECT COUNT(*) FROM ingestion_jobs")
                assert cur.fetchone() == (1,)
                cur.execute("SELECT id FROM sources WHERE id = %s", (source_b,))
                assert cur.fetchone() is None

                cur.execute("SET app.tenant_id = %s", (str(tenant_b),))
                cur.execute("SELECT COUNT(*) FROM sources")
                assert cur.fetchone() == (1,)
                cur.execute("SELECT COUNT(*) FROM ingestion_jobs")
                assert cur.fetchone() == (1,)
                cur.execute("SELECT id FROM ingestion_jobs WHERE id = %s", (job_a,))
                assert cur.fetchone() is None

                cur.execute("RESET app.tenant_id")
                cur.execute("SELECT COUNT(*) FROM sources")
                assert cur.fetchone() == (0,)
    finally:
        pg.stop()
