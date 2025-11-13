"""Add ``tenant_id`` references to all critical domain tables."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy import column, table
from sqlalchemy.dialects import postgresql

revision = "012_add_tenant_ids"
down_revision = "011_add_auth_tables"
branch_labels = None
depends_on = None


_UUID = postgresql.UUID(as_uuid=True)


def _ensure_default_organization(conn) -> UUID:
    """Return the identifier for the default organization, creating it if needed."""

    result = conn.execute(
        sa.text("SELECT id FROM organizations WHERE subdomain = :subdomain LIMIT 1"),
        {"subdomain": "default"},
    ).scalar()
    if result:
        return result

    return conn.execute(
        sa.text(
            """
            INSERT INTO organizations (name, subdomain)
            VALUES (:name, :subdomain)
            RETURNING id
            """
        ),
        {"name": "Default Organization", "subdomain": "default"},
    ).scalar()


def _add_tenant_column(table: str) -> None:
    op.add_column(table, sa.Column("tenant_id", _UUID, nullable=True))


def _set_tenant_values(conn, table_name: str, tenant_id: UUID) -> None:
    tbl = table(table_name, column("tenant_id"))
    conn.execute(
        tbl.update().where(tbl.c.tenant_id.is_(None)).values(tenant_id=tenant_id)
    )


def _set_not_null(table: str) -> None:
    op.alter_column(table, "tenant_id", existing_type=_UUID, nullable=False)


def _add_tenant_fk(table: str) -> None:
    op.create_foreign_key(
        f"fk_{table}_tenant",
        source_table=table,
        referent_table="organizations",
        local_cols=["tenant_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    conn = op.get_bind()
    tenant_id = _ensure_default_organization(conn)

    tables: Iterable[str] = (
        "connector_definitions",
        "sources",
        "ingestion_jobs",
        "documents",
        "document_versions",
        "chunks",
        "feedbacks",
        "agents",
        "agent_versions",
        "agent_tests",
        "agent_channel_configs",
        "conversations",
        "conversation_participants",
        "conversation_messages",
    )

    for table_name in tables:
        _add_tenant_column(table_name)

    op.drop_constraint("documents_path_key", "documents", type_="unique")
    op.drop_constraint("agents_slug_key", "agents", type_="unique")

    for table_name in tables:
        _set_tenant_values(conn, table_name, tenant_id)
        _set_not_null(table_name)
        _add_tenant_fk(table_name)

    op.create_unique_constraint(
        "uq_documents_tenant_path", "documents", ["tenant_id", "path"]
    )
    op.create_unique_constraint(
        "uq_agents_tenant_slug", "agents", ["tenant_id", "slug"]
    )

    op.drop_index("idx_connector_definitions_type", table_name="connector_definitions")
    op.create_index(
        "idx_connector_definitions_tenant_type",
        "connector_definitions",
        ["tenant_id", "type"],
    )

    op.drop_index("idx_sources_active", table_name="sources")
    op.drop_index("idx_sources_path_active", table_name="sources")
    op.drop_index("idx_sources_url_active", table_name="sources")
    op.create_index(
        "idx_sources_tenant_active",
        "sources",
        ["tenant_id", "active"],
    )
    op.create_index(
        "idx_sources_tenant_path_active",
        "sources",
        ["tenant_id", "path"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_sources_tenant_url_active",
        "sources",
        ["tenant_id", "url"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_index("idx_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_source_id", table_name="ingestion_jobs")
    op.create_index(
        "idx_ingestion_jobs_tenant_status",
        "ingestion_jobs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "idx_ingestion_jobs_tenant_source",
        "ingestion_jobs",
        ["tenant_id", "source_id"],
    )

    op.create_index(
        "idx_documents_tenant_source",
        "documents",
        ["tenant_id", "source_id"],
    )
    op.create_index(
        "idx_document_versions_tenant_document",
        "document_versions",
        ["tenant_id", "document_id"],
    )

    op.drop_index("idx_chunks_doc", table_name="chunks")
    op.create_index(
        "idx_chunks_tenant_doc",
        "chunks",
        ["tenant_id", "doc_id", "chunk_index"],
    )

    op.drop_index("idx_feedbacks_created_at", table_name="feedbacks")
    op.drop_index("idx_feedbacks_helpful", table_name="feedbacks")
    op.create_index(
        "idx_feedbacks_tenant_created_at",
        "feedbacks",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_feedbacks_tenant_helpful",
        "feedbacks",
        ["tenant_id", "helpful"],
    )

    op.create_index(
        "idx_agents_tenant_active",
        "agents",
        ["tenant_id", "is_active"],
    )

    op.drop_index("idx_agent_versions_agent_id", table_name="agent_versions")
    op.create_index(
        "idx_agent_versions_tenant_agent",
        "agent_versions",
        ["tenant_id", "agent_id"],
    )

    op.drop_index("idx_agent_tests_agent_id", table_name="agent_tests")
    op.drop_index("idx_agent_tests_agent_version_id", table_name="agent_tests")
    op.create_index(
        "idx_agent_tests_tenant_agent",
        "agent_tests",
        ["tenant_id", "agent_id"],
    )
    op.create_index(
        "idx_agent_tests_tenant_agent_version",
        "agent_tests",
        ["tenant_id", "agent_version_id"],
    )

    op.create_index(
        "idx_agent_channel_configs_tenant_agent",
        "agent_channel_configs",
        ["tenant_id", "agent_id"],
    )

    op.drop_index("idx_conversations_agent", table_name="conversations")
    op.drop_index("idx_conversations_follow_up", table_name="conversations")
    op.drop_index("idx_conversations_escalated", table_name="conversations")
    op.create_index(
        "idx_conversations_tenant_agent",
        "conversations",
        ["tenant_id", "agent_id", "channel"],
    )
    op.create_index(
        "idx_conversations_tenant_follow_up",
        "conversations",
        ["tenant_id", "follow_up_at"],
        postgresql_where=sa.text("follow_up_at IS NOT NULL"),
    )
    op.create_index(
        "idx_conversations_tenant_escalated",
        "conversations",
        ["tenant_id", "is_escalated"],
        postgresql_where=sa.text("is_escalated"),
    )

    op.drop_index(
        "idx_conversation_participants_conversation",
        table_name="conversation_participants",
    )
    op.drop_index(
        "idx_conversation_participants_role",
        table_name="conversation_participants",
    )
    op.create_index(
        "idx_conversation_participants_tenant_conversation",
        "conversation_participants",
        ["tenant_id", "conversation_id"],
    )
    op.create_index(
        "idx_conversation_participants_tenant_role",
        "conversation_participants",
        ["tenant_id", "conversation_id", "role"],
    )

    op.drop_index(
        "idx_conversation_messages_conversation",
        table_name="conversation_messages",
    )
    op.create_index(
        "idx_conversation_messages_tenant_conversation",
        "conversation_messages",
        ["tenant_id", "conversation_id", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_conversation_messages_tenant_conversation",
        table_name="conversation_messages",
    )
    op.drop_index(
        "idx_conversation_participants_tenant_role",
        table_name="conversation_participants",
    )
    op.drop_index(
        "idx_conversation_participants_tenant_conversation",
        table_name="conversation_participants",
    )
    op.drop_index("idx_conversations_tenant_escalated", table_name="conversations")
    op.drop_index("idx_conversations_tenant_follow_up", table_name="conversations")
    op.drop_index("idx_conversations_tenant_agent", table_name="conversations")
    op.drop_index(
        "idx_agent_channel_configs_tenant_agent",
        table_name="agent_channel_configs",
    )
    op.drop_index("idx_agent_tests_tenant_agent_version", table_name="agent_tests")
    op.drop_index("idx_agent_tests_tenant_agent", table_name="agent_tests")
    op.create_index(
        "idx_agent_tests_agent_version_id",
        "agent_tests",
        ["agent_version_id"],
    )
    op.create_index(
        "idx_agent_tests_agent_id",
        "agent_tests",
        ["agent_id"],
    )
    op.drop_index("idx_agent_versions_tenant_agent", table_name="agent_versions")
    op.create_index(
        "idx_agent_versions_agent_id",
        "agent_versions",
        ["agent_id"],
    )
    op.drop_index("idx_agents_tenant_active", table_name="agents")
    op.drop_index("idx_feedbacks_tenant_helpful", table_name="feedbacks")
    op.drop_index("idx_feedbacks_tenant_created_at", table_name="feedbacks")
    op.create_index(
        "idx_feedbacks_helpful",
        "feedbacks",
        ["helpful"],
    )
    op.create_index(
        "idx_feedbacks_created_at",
        "feedbacks",
        ["created_at"],
    )
    op.drop_index("idx_chunks_tenant_doc", table_name="chunks")
    op.create_index("idx_chunks_doc", "chunks", ["doc_id", "chunk_index"])
    op.drop_index(
        "idx_document_versions_tenant_document",
        table_name="document_versions",
    )
    op.drop_index("idx_documents_tenant_source", table_name="documents")
    op.drop_index("idx_ingestion_jobs_tenant_source", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_tenant_status", table_name="ingestion_jobs")
    op.create_index(
        "idx_ingestion_jobs_source_id",
        "ingestion_jobs",
        ["source_id"],
    )
    op.create_index(
        "idx_ingestion_jobs_status",
        "ingestion_jobs",
        ["status"],
    )
    op.drop_index("idx_sources_tenant_url_active", table_name="sources")
    op.drop_index("idx_sources_tenant_path_active", table_name="sources")
    op.drop_index("idx_sources_tenant_active", table_name="sources")
    op.create_index(
        "idx_sources_url_active",
        "sources",
        ["url"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_sources_path_active",
        "sources",
        ["path"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_sources_active", "sources", ["active"])
    op.drop_index(
        "idx_connector_definitions_tenant_type",
        table_name="connector_definitions",
    )
    op.create_index(
        "idx_connector_definitions_type",
        "connector_definitions",
        ["type"],
    )

    op.drop_constraint("uq_agents_tenant_slug", "agents", type_="unique")
    op.drop_constraint("uq_documents_tenant_path", "documents", type_="unique")

    tables: Iterable[str] = (
        "conversation_messages",
        "conversation_participants",
        "conversations",
        "agent_channel_configs",
        "agent_tests",
        "agent_versions",
        "agents",
        "feedbacks",
        "chunks",
        "document_versions",
        "documents",
        "ingestion_jobs",
        "sources",
        "connector_definitions",
    )

    for table_name in tables:
        op.drop_constraint(f"fk_{table_name}_tenant", table_name, type_="foreignkey")
        op.alter_column(table_name, "tenant_id", existing_type=_UUID, nullable=True)
        op.drop_column(table_name, "tenant_id")

    op.create_unique_constraint("agents_slug_key", "agents", ["slug"])
    op.create_unique_constraint("documents_path_key", "documents", ["path"])
