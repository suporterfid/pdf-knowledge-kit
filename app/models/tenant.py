"""Tenant-related SQLAlchemy models.

The models defined here represent the core multi-tenant entities used by the
platform: organizations and their users.  They mirror the DDL maintained in the
migrations (see ``app/migrations/004_create_multi_tenant_tables.py``) to ensure
consistency between ORM usage and raw SQL migrations.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class Organization(Base):
    """Represents a tenant organization in the platform.

    Attributes:
        id: Primary key generated via ``gen_random_uuid`` in Postgres.
        name: Display name of the organization.
        subdomain: Unique subdomain used for tenant isolation.
        plan_type: Current subscription tier for the organization.
        users: Collection of users that belong to this organization.
    """

    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_organizations_subdomain_unique", "subdomain", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(length=255), nullable=False)
    plan_type: Mapped[str] = mapped_column(
        String(length=64),
        nullable=False,
        default="free",
        server_default=text("'free'"),
    )

    users: Mapped[List["User"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class User(Base):
    """Represents a user that belongs to an organization.

    Attributes:
        id: Primary key generated via ``gen_random_uuid`` in Postgres.
        organization_id: Foreign key that links to the owning organization.
        email: Unique e-mail address used for authentication.
        password_hash: Secure hash of the user's password.
        name: Friendly name shown in the UI and logs.
        organization: Relationship back to :class:`Organization`.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_unique", "email", unique=True),
        Index("ix_users_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(length=320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(length=255), nullable=False)
    name: Mapped[str] = mapped_column(String(length=255), nullable=False)

    organization: Mapped[Organization] = relationship(
        back_populates="users",
        lazy="joined",
    )


__all__ = ["Organization", "User"]
