"""Tests for ensuring the bundled sample document is ingested during seeding."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from seed import SeedConfig, _ensure_sample_document


class _DummyCursor:
    """Cursor stub that records the last executed query and yields results."""

    def __init__(self, results: list[tuple[Any, ...]]):
        self._results = results
        self._last_query: str | None = None

    def __enter__(self) -> "_DummyCursor":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        return None

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        self._last_query = query

    def fetchone(self) -> tuple[Any, ...] | None:
        if self._last_query and "FROM documents" in self._last_query:
            if self._results:
                return self._results.pop(0)
            return None
        return None


class _DummyConnection:
    """Connection stub that vends :class:`_DummyCursor` instances."""

    def __init__(self, results: list[tuple[Any, ...]]):
        self._results = results
        self.cursors: list[_DummyCursor] = []

    def __enter__(self) -> "_DummyConnection":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        return None

    def cursor(self) -> _DummyCursor:
        cursor = _DummyCursor(self._results)
        self.cursors.append(cursor)
        return cursor


@pytest.fixture(name="seed_config")
def _seed_config() -> SeedConfig:
    """Return a ``SeedConfig`` with deterministic settings for tests."""

    return SeedConfig(
        db_url="postgresql://user:pass@localhost:5432/testdb",
        sqlalchemy_url="postgresql+psycopg://user:pass@localhost:5432/testdb",
        docs_dir=None,
        urls=[],
        use_ocr=True,
        ocr_lang="por",
        org_name="Example",
        org_subdomain="example",
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="secret",
    )


def _sample_path() -> Path:
    return Path(__file__).resolve().parents[1] / "sample_data" / "example_document.pdf"


def test_ensure_sample_document_skips_when_present(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    seed_config: SeedConfig,
) -> None:
    """When the document already exists, ingestion should be skipped."""

    results: list[tuple[Any, ...]] = [(1,)]

    def _connect(dsn: str) -> _DummyConnection:
        assert dsn == seed_config.db_url
        return _DummyConnection(results)

    monkeypatch.setattr(psycopg, "connect", _connect)

    called = False

    def _unexpected_ingest(*_args, **_kwargs):  # pragma: no cover - defensive
        nonlocal called
        called = True
        raise AssertionError("ingest_local should not be called when document exists")

    monkeypatch.setattr("seed.ingestion_service.ingest_local", _unexpected_ingest)
    monkeypatch.setattr("seed.ingestion_service.wait_for_job", lambda *_: None)

    tenant_id = uuid.uuid4()
    with caplog.at_level(logging.INFO):
        _ensure_sample_document(seed_config, tenant_id)

    assert not called
    assert "already present" in caplog.text


def test_ensure_sample_document_ingests_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    seed_config: SeedConfig,
) -> None:
    """When the document is missing, ingestion should be triggered."""

    results: list[tuple[Any, ...]] = []

    def _connect(dsn: str) -> _DummyConnection:
        assert dsn == seed_config.db_url
        return _DummyConnection(results)

    monkeypatch.setattr(psycopg, "connect", _connect)

    ingested: list[tuple[Path, uuid.UUID, bool, str | None]] = []
    job_id = uuid.uuid4()

    def _fake_ingest(
        path: Path,
        *,
        tenant_id: uuid.UUID,
        use_ocr: bool,
        ocr_lang: str | None,
    ) -> uuid.UUID:
        ingested.append((path, tenant_id, use_ocr, ocr_lang))
        return job_id

    waited: list[uuid.UUID] = []

    def _fake_wait(received_job_id: uuid.UUID) -> None:
        waited.append(received_job_id)

    monkeypatch.setattr("seed.ingestion_service.ingest_local", _fake_ingest)
    monkeypatch.setattr("seed.ingestion_service.wait_for_job", _fake_wait)

    tenant_id = uuid.uuid4()
    with caplog.at_level(logging.INFO):
        _ensure_sample_document(seed_config, tenant_id)

    assert ingested, "Expected the sample document to be ingested"
    path, recorded_tenant, use_ocr, ocr_lang = ingested[0]
    assert path == _sample_path().resolve()
    assert recorded_tenant == tenant_id
    assert use_ocr is seed_config.use_ocr
    assert ocr_lang == seed_config.ocr_lang
    assert waited == [job_id]
    assert "Sample document ingested" in caplog.text
