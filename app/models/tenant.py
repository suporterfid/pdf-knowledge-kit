"""Tenant-related SQLAlchemy models.

The models defined here represent the core multi-tenant entities used by the
platform: organizations and their users.  They mirror the DDL maintained in the
migrations (see ``app/migrations/004_create_multi_tenant_tables.py``) to ensure
consistency between ORM usage and raw SQL migrations.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import List

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


def _utcnow() -> dt.datetime:
    """Return the current UTC timestamp with timezone awareness."""

    return dt.datetime.now(dt.timezone.utc)


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
        default=uuid.uuid4,
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
    invites: Mapped[List["UserInvite"]] = relationship(
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
        default=uuid.uuid4,
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
    role: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        default="viewer",
        server_default=text("'viewer'"),
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    organization: Mapped[Organization] = relationship(
        back_populates="users",
        lazy="joined",
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserInvite(Base):
    """Invitation issued to onboard a user into an organization."""

    __tablename__ = "user_invites"
    __table_args__ = (
        Index("ix_user_invites_token_unique", "token", unique=True),
        Index("ix_user_invites_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(length=320), nullable=False)
    role: Mapped[str] = mapped_column(String(length=32), nullable=False)
    token: Mapped[str] = mapped_column(String(length=255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    organization: Mapped[Organization] = relationship(back_populates="invites")


class RefreshToken(Base):
    """Refresh tokens issued during interactive authentication flows."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(length=255), nullable=False)
    issued_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(length=255))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


__all__ = ["Organization", "User", "UserInvite", "RefreshToken"]
