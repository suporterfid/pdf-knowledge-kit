"""Create multi-tenant core tables for organizations and users."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "004_create_multi_tenant_tables"
down_revision = None
branch_labels = None
depends_on = None


_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Create ``organizations`` and ``users`` tables with supporting indexes."""

    op.create_table(
        "organizations",
        sa.Column(
            "id",
            _UUID,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subdomain", sa.String(length=255), nullable=False),
        sa.Column(
            "plan_type",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'free'"),
        ),
    )
    op.create_index(
        "ix_organizations_subdomain_unique",
        "organizations",
        ["subdomain"],
        unique=True,
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            _UUID,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            _UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
    )
    op.create_index(
        "ix_users_email_unique",
        "users",
        ["email"],
        unique=True,
    )
    op.create_index(
        "ix_users_organization_id",
        "users",
        ["organization_id"],
    )


def downgrade() -> None:
    """Remove ``users`` and ``organizations`` tables and related indexes."""

    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_index("ix_users_email_unique", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_organizations_subdomain_unique", table_name="organizations")
    op.drop_table("organizations")
