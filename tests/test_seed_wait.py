"""Tests for the ``wait_for_database`` helper."""

from __future__ import annotations

import psycopg
import pytest

from seed import wait_for_database


class _DummyCursor:
    """Simple cursor stub that satisfies the context manager protocol."""

    def __enter__(self) -> "_DummyCursor":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # pragma: no cover - trivial
        return None

    def execute(self, query: str) -> None:
        return None


class _DummyConnection:
    """Simple connection stub that returns a dummy cursor."""

    def __enter__(self) -> "_DummyConnection":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # pragma: no cover - trivial
        return None

    def cursor(self) -> _DummyCursor:
        return _DummyCursor()


def test_wait_for_database_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """``wait_for_database`` should exit after a successful attempt."""

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

    attempts: list[tuple[str, int]] = []

    def _connect(dsn: str, connect_timeout: int) -> _DummyConnection:
        attempts.append((dsn, connect_timeout))
        return _DummyConnection()

    monkeypatch.setattr(psycopg, "connect", _connect)

    wait_for_database(max_attempts=3, delay=0.0)

    assert attempts == [("postgresql://user:pass@localhost:5432/testdb", 5)]


def test_wait_for_database_raises_after_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper should raise ``RuntimeError`` after the configured attempts."""

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

    call_count = 0

    class _ExpectedError(RuntimeError):
        pass

    def _connect(dsn: str, connect_timeout: int) -> None:
        nonlocal call_count
        call_count += 1
        raise _ExpectedError("boom")

    monkeypatch.setattr(psycopg, "connect", _connect)

    with pytest.raises(RuntimeError, match="Database did not become ready in time"):
        wait_for_database(max_attempts=2, delay=0.0)

    assert call_count == 2
