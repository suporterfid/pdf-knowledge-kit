from __future__ import annotations

# ruff: noqa: S101
from collections.abc import Iterable
from datetime import datetime, timezone
from threading import Event
from typing import Any
from uuid import uuid4

import pytest
from app.ingestion.connectors.sql import SqlConnector
from app.ingestion.models import Source, SourceType
from app.ingestion.parsers import Chunk


class _FakeCursor:
    def __init__(
        self,
        rows: Iterable[dict[str, Any]],
        executions: list[tuple[str, dict[str, Any] | None]],
    ):
        self._rows = list(rows)
        self._executions = executions

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        self._executions.append((sql, params))

    def __iter__(self):
        return iter(self._rows)


class _FakeConnection:
    def __init__(self, row_batches: list[list[dict[str, Any]]]):
        self._row_batches = list(row_batches)
        self.executions: list[tuple[str, dict[str, Any] | None]] = []

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def cursor(self, *, row_factory=None):  # noqa: D401 - matches psycopg signature
        rows = self._row_batches.pop(0) if self._row_batches else []
        return _FakeCursor(rows, self.executions)


@pytest.fixture()
def fake_chunk(monkeypatch):
    captured: list[dict[str, Any]] = []

    def _chunk(text: str, **kwargs: Any):
        metadata = kwargs.get("extra_metadata") or {}
        captured.append({"text": text, **kwargs})
        return [
            Chunk(
                content=text,
                source_path=kwargs["source_path"],
                mime_type=kwargs["mime_type"],
                page_number=kwargs.get("page_number"),
                extra=metadata,
            )
        ]

    monkeypatch.setattr("app.ingestion.connectors.sql.chunk_text", _chunk)
    return captured


def test_sql_connector_streams_rows_and_updates_state(monkeypatch, fake_chunk):
    row = {
        "id": 7,
        "body": "Important note",
        "updated_at": datetime(2024, 1, 1, 12, 0, 0),
        "category": "announcements",
    }
    fake_conn = _FakeConnection([[row]])
    monkeypatch.setattr(
        "app.ingestion.connectors.sql.psycopg.connect", lambda *a, **k: fake_conn
    )

    source = Source(
        id=uuid4(),
        tenant_id=uuid4(),
        type=SourceType.DATABASE,
        created_at=datetime.now(timezone.utc),
        params={
            "dsn": "postgresql://example",
            "queries": [
                {
                    "name": "recent",
                    "table": "messages",
                    "sql": "SELECT * FROM messages WHERE updated_at > %(since)s",
                    "text_column": "body",
                    "id_column": "id",
                    "cursor_column": "updated_at",
                    "cursor_param": "since",
                    "params": {"limit": 50},
                    "extra_metadata_fields": ["category"],
                }
            ],
        },
        credentials={"username": "dbuser"},
        sync_state={"queries": {"recent": {"cursor": "2023-12-01T00:00:00"}}},
    )

    connector = SqlConnector(source)
    records = list(connector.stream())

    assert len(records) == 1
    record = records[0]
    assert record.document_path == "recent/7"
    assert record.page_count == 1
    assert record.document_sync_state == {
        "query": "recent",
        "cursor_column": "updated_at",
        "cursor": row["updated_at"].isoformat(),
        "row_id": row["id"],
    }
    assert record.extra_info == {"query": "recent", "row_id": row["id"]}

    assert fake_chunk[0]["extra_metadata"]["table"] == "recent"
    assert fake_chunk[0]["extra_metadata"]["connector"] == "sql"
    assert fake_chunk[0]["extra_metadata"]["query"] == "recent"
    assert fake_chunk[0]["extra_metadata"]["row_id"] == row["id"]
    assert (
        fake_chunk[0]["extra_metadata"]["updated_at"] == row["updated_at"].isoformat()
    )
    assert fake_chunk[0]["extra_metadata"]["category"] == "announcements"
    assert fake_chunk[0]["source_path"] == "recent/7"

    # Cursor was injected into the executed parameters
    _, executed_params = fake_conn.executions[0]
    assert executed_params == {"limit": 50, "since": "2023-12-01T00:00:00"}

    assert connector.job_metadata == {"queries": 1, "rows": 1, "chunks": 1}
    assert (
        connector.next_sync_state["queries"]["recent"]["cursor"]
        == row["updated_at"].isoformat()
    )


def test_sql_connector_honours_cancellation(monkeypatch, fake_chunk):
    rows = [
        {"id": 1, "body": "A", "updated_at": datetime(2024, 1, 1, 0, 0)},
        {"id": 2, "body": "B", "updated_at": datetime(2024, 1, 1, 0, 1)},
    ]
    fake_conn = _FakeConnection([rows])
    monkeypatch.setattr(
        "app.ingestion.connectors.sql.psycopg.connect", lambda *a, **k: fake_conn
    )

    source = Source(
        id=uuid4(),
        tenant_id=uuid4(),
        type=SourceType.DATABASE,
        created_at=datetime.now(timezone.utc),
        params={
            "dsn": "postgresql://example",
            "queries": [
                {
                    "name": "recent",
                    "sql": "SELECT * FROM t",
                    "text_column": "body",
                    "id_column": "id",
                    "cursor_column": "updated_at",
                }
            ],
        },
    )

    connector = SqlConnector(source)
    cancel = Event()

    emitted = []
    for record in connector.stream(cancel):
        emitted.append(record)
        cancel.set()

    assert len(emitted) == 1
    assert (
        connector.next_sync_state["queries"]["recent"]["cursor"]
        == rows[0]["updated_at"].isoformat()
    )
