from __future__ import annotations

import pathlib

import psycopg
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from app.ingestion.service import SCHEMA_PATH, ensure_schema


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

        engine = sa.create_engine(make_url(pg.url()).set(drivername="postgresql+psycopg"))
        try:
            with engine.connect() as connection:
                inspector = sa.inspect(connection)
                tables = inspector.get_table_names()
                assert "organizations" in tables
                assert "users" in tables

                org_columns = {col["name"] for col in inspector.get_columns("organizations")}
                assert {"id", "name", "subdomain", "plan_type"}.issubset(org_columns)

                user_columns = {col["name"] for col in inspector.get_columns("users")}
                assert {"id", "organization_id", "email", "password_hash", "name"}.issubset(
                    user_columns
                )

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
        finally:
            engine.dispose()

        with psycopg.connect(pg.url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM app_python_migrations WHERE id = %s",
                    ("004_create_multi_tenant_tables",),
                )
                assert cur.fetchone()
    finally:
        pg.stop()
