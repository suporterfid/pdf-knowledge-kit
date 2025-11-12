"""Helpers for configuring SQLAlchemy engine and session factories."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import uuid

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from . import Base


def get_engine(database_url: str | None = None, **kwargs: object) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        database_url: Optional database URL. When ``None`` the ``DATABASE_URL``
            environment variable is used.
        **kwargs: Additional keyword arguments forwarded to
            :func:`sqlalchemy.create_engine`.

    Returns:
        Configured SQLAlchemy :class:`~sqlalchemy.engine.Engine` instance.
    """

    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    engine = create_engine(url, **kwargs)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record):  # pragma: no cover - dialect hook
            dbapi_connection.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def get_sessionmaker(database_url: str | None = None, **kwargs: object) -> sessionmaker[Session]:
    """Return a session factory bound to the configured engine."""

    engine = get_engine(database_url=database_url, **kwargs)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(database_url: str | None = None, **kwargs: object) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    factory = get_sessionmaker(database_url=database_url, **kwargs)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "get_engine", "get_sessionmaker", "session_scope"]
