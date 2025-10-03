"""SQLAlchemy declarative base and tenant-facing models.

This package hosts the SQLAlchemy models used across the backend.  It exposes a
single declarative ``Base`` class that other modules can import when creating
tables or writing migrations in Python.  Individual models live in dedicated
modules within this package.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""


# Re-export core tenant models for convenience so callers can import them via
# ``from app.models import Organization`` instead of touching private modules.
from .tenant import Organization, User


__all__ = [
    "Base",
    "Organization",
    "User",
]
