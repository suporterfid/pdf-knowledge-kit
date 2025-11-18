"""Add authentication metadata tables and columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "011_add_auth_tables"
down_revision = "004_create_multi_tenant_tables"
branch_labels = None
depends_on = None


_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Check if tables/columns already exist (schema.sql creates them)
    with op._conn.cursor() as cur:
        # Check if user_invites table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'user_invites'
            );
        """)
        tables_exist = cur.fetchone()[0]

        if tables_exist:
            # Tables and columns already created by schema.sql, skip
            return

    # Legacy migration code for older databases
    # This won't run on fresh installs as schema.sql creates everything
    # Adding columns to users table (note: _PsycopgOperations doesn't have add_column)
    # So we'll use raw SQL
    with op._conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'viewer',
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true,
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now());
        """)

    op.create_table(
        "user_invites",
        sa.Column(
            "id",
            _UUID,
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            _UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
    )
    op.create_index(
        "ix_user_invites_token_unique",
        "user_invites",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_user_invites_org",
        "user_invites",
        ["organization_id"],
    )

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            _UUID,
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            _UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_user_invites_org", table_name="user_invites")
    op.drop_index("ix_user_invites_token_unique", table_name="user_invites")
    op.drop_table("user_invites")

    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
