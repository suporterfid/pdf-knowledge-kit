"""Integration-style tests for the seeding helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pytest
from app.models import Base, Organization, User
from app.security import verify_password
from seed import SeedConfig, _ensure_sample_document, _provision_tenant
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker


@dataclass(slots=True)
class SeedTestContext:
    """Holds the resources required to exercise the seed helpers."""

    session_factory: sessionmaker[Session]
    config: SeedConfig
    doc_store: dict[str, Any]


class _MemoryCursor:
    """Very small stub mimicking the parts of ``psycopg.Cursor`` we rely on."""

    def __init__(self, store: dict[str, Any]):
        self._store = store
        self._last_query: str | None = None

    def __enter__(self) -> "_MemoryCursor":  # pragma: no cover - trivial
        return self

    def __exit__(
        self, exc_type: object, exc: object, tb: object
    ) -> None:  # pragma: no cover - trivial
        return None

    def execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> None:  # pragma: no cover - simple assignment
        self._last_query = query

    def fetchone(self) -> tuple[int, ...] | None:
        if self._last_query and "FROM documents" in self._last_query:
            if self._store.get("present"):
                return (1,)
            return None
        return None


class _MemoryConnection:
    """Connection stub that vends :class:`_MemoryCursor` objects."""

    def __init__(self, store: dict[str, Any]):
        self._store = store

    def __enter__(self) -> "_MemoryConnection":  # pragma: no cover - trivial
        return self

    def __exit__(
        self, exc_type: object, exc: object, tb: object
    ) -> None:  # pragma: no cover - trivial
        return None

    def cursor(self) -> _MemoryCursor:
        return _MemoryCursor(self._store)


@pytest.fixture()
def seed_test_context(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[SeedTestContext]:
    """Create a temporary SQLite database and ``SeedConfig`` for tests."""

    db_dir = tmp_path_factory.mktemp("seed-tests")
    db_path = db_dir / "seed.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(db_url, future=True)

    @event.listens_for(engine, "connect")
    def _register_uuid(
        connection: Any, _record: Any
    ) -> None:  # pragma: no cover - helper wiring
        connection.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    config = SeedConfig(
        db_url=db_url,
        sqlalchemy_url=db_url,
        docs_dir=None,
        urls=[],
        use_ocr=False,
        ocr_lang=None,
        org_name="Seed Tenant",
        org_subdomain="seed-demo",
        admin_name="Seed Admin",
        admin_email="admin@seed.example",
        admin_password="Secret123!",
    )

    store: dict[str, Any] = {"present": False}

    context = SeedTestContext(
        session_factory=session_factory,
        config=config,
        doc_store=store,
    )

    try:
        yield context
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _install_psycopg_stub(
    monkeypatch: pytest.MonkeyPatch, store: dict[str, Any]
) -> None:
    """Replace ``psycopg.connect`` with a deterministic in-memory stub."""

    def _connect(dsn: str) -> _MemoryConnection:
        return _MemoryConnection(store)

    monkeypatch.setattr("seed.psycopg.connect", _connect)


def test_seed_first_run_creates_entities_and_ingests(
    seed_test_context: SeedTestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seeding should create the tenant/admin and ingest the sample document."""

    _install_psycopg_stub(monkeypatch, seed_test_context.doc_store)

    ingested: list[tuple[Path, uuid.UUID, bool, str | None]] = []
    job_id = uuid.uuid4()

    def _fake_ingest_local(
        path: Path,
        *,
        tenant_id: uuid.UUID,
        use_ocr: bool,
        ocr_lang: str | None,
    ) -> uuid.UUID:
        seed_test_context.doc_store["present"] = True
        ingested.append((path, tenant_id, use_ocr, ocr_lang))
        return job_id

    waited: list[uuid.UUID] = []

    def _fake_wait(received_job_id: uuid.UUID) -> None:
        waited.append(received_job_id)

    monkeypatch.setattr("seed.ingestion_service.ingest_local", _fake_ingest_local)
    monkeypatch.setattr("seed.ingestion_service.wait_for_job", _fake_wait)

    tenant_id = _provision_tenant(seed_test_context.session_factory, seed_test_context.config)

    with seed_test_context.session_factory() as session:
        organization = session.execute(select(Organization)).scalar_one()
        user = session.execute(select(User)).scalar_one()

    assert organization.subdomain == seed_test_context.config.org_subdomain
    assert user.organization_id == tenant_id
    assert verify_password(seed_test_context.config.admin_password, user.password_hash)

    _ensure_sample_document(seed_test_context.config, tenant_id)

    assert len(ingested) == 1
    path, recorded_tenant, use_ocr, ocr_lang = ingested[0]
    assert recorded_tenant == tenant_id
    assert path.name == "example_document.pdf"
    assert use_ocr is seed_test_context.config.use_ocr
    assert ocr_lang is seed_test_context.config.ocr_lang
    assert waited == [job_id]


def test_seed_second_run_is_idempotent(
    seed_test_context: SeedTestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running the seed helpers twice should avoid duplicates and re-ingestion."""

    _install_psycopg_stub(monkeypatch, seed_test_context.doc_store)

    job_id = uuid.uuid4()
    ingestions: list[uuid.UUID] = []
    waits: list[uuid.UUID] = []

    def _fake_ingest(
        path: Path,
        *,
        tenant_id: uuid.UUID,
        use_ocr: bool,
        ocr_lang: str | None,
    ) -> uuid.UUID:
        seed_test_context.doc_store["present"] = True
        ingestions.append(tenant_id)
        return job_id

    def _fake_wait(received_job_id: uuid.UUID) -> None:
        waits.append(received_job_id)

    monkeypatch.setattr("seed.ingestion_service.ingest_local", _fake_ingest)
    monkeypatch.setattr("seed.ingestion_service.wait_for_job", _fake_wait)

    first_tenant_id = _provision_tenant(
        seed_test_context.session_factory, seed_test_context.config
    )
    _ensure_sample_document(seed_test_context.config, first_tenant_id)

    assert ingestions == [first_tenant_id]
    assert waits == [job_id]

    ingestions.clear()
    waits.clear()

    second_tenant_id = _provision_tenant(
        seed_test_context.session_factory, seed_test_context.config
    )
    _ensure_sample_document(seed_test_context.config, second_tenant_id)

    assert second_tenant_id == first_tenant_id
    assert not ingestions
    assert not waits

    with seed_test_context.session_factory() as session:
        organizations = session.execute(select(Organization)).scalars().all()
        users = session.execute(select(User)).scalars().all()

    assert len(organizations) == 1
    assert len(users) == 1
    assert verify_password(seed_test_context.config.admin_password, users[0].password_hash)
