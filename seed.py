"""Utility script to bootstrap the database with a demo tenant and content."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
import psycopg
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import apply_tenant_settings
from app.ingestion import service as ingestion_service
from app.ingestion.service import ensure_schema
from app.models import Organization, User
from app.models.session import get_sessionmaker
from app.security import hash_password

logger = logging.getLogger("seed")

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".md", ".txt", ".docx", ".csv", ".xlsx")


@dataclass(slots=True)
class SeedConfig:
    """Configuration derived from the environment for the seed process."""

    db_url: str
    sqlalchemy_url: str
    docs_dir: Path | None
    urls: list[str]
    use_ocr: bool
    ocr_lang: str | None
    org_name: str
    org_subdomain: str
    admin_name: str
    admin_email: str
    admin_password: str


def _to_bool(value: str | None) -> bool:
    """Parse a truthy string value into ``bool``."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_sqlalchemy_url(db_url: str) -> str:
    """Ensure the SQLAlchemy URL uses the ``psycopg`` driver."""

    if db_url.startswith("postgresql+psycopg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return db_url


def _safe_url(db_url: str) -> str:
    """Return a version of ``db_url`` with any password redacted."""

    try:
        parsed = make_url(db_url)
    except Exception:  # pragma: no cover - defensive fallback
        return db_url
    if parsed.password is None:
        return db_url
    redacted = parsed.set(password="***")
    return redacted.render_as_string(hide_password=False)


def _build_database_url() -> str:
    """Compute the database URL from ``DATABASE_URL`` or ``PG*`` variables."""

    direct = os.getenv("DATABASE_URL")
    if direct:
        return direct

    host = os.getenv("PGHOST")
    port = os.getenv("PGPORT", "5432")
    database = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")

    if not all([host, database, user]):
        raise RuntimeError(
            "DATABASE_URL is not configured and PGHOST/PGDATABASE/PGUSER are missing."
        )

    auth = user
    if password:
        auth = f"{user}:{password}"
    return f"postgresql://{auth}@{host}:{port}/{database}"


def _load_config() -> SeedConfig:
    """Load seed configuration from environment variables."""

    db_url = _build_database_url()
    sqlalchemy_url = _as_sqlalchemy_url(db_url)

    docs_dir_env = os.getenv("DOCS_DIR")
    docs_dir = Path(docs_dir_env).expanduser() if docs_dir_env else None
    if docs_dir and not docs_dir.exists():
        logger.warning("Docs directory %s does not exist; skipping local ingestion.", docs_dir)
        docs_dir = None

    urls_file_env = os.getenv("URLS_FILE")
    urls: list[str] = []
    if urls_file_env:
        urls_path = Path(urls_file_env).expanduser()
        if urls_path.exists():
            urls = [
                line.strip()
                for line in urls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            logger.info("URL list file %s not found; skipping URL ingestion.", urls_path)

    use_ocr = _to_bool(os.getenv("ENABLE_OCR"))
    ocr_lang = os.getenv("OCR_LANG") if use_ocr else None

    org_name = os.getenv("SEED_ORGANIZATION_NAME", "Demo Tenant").strip()
    org_subdomain = os.getenv("SEED_ORGANIZATION_SUBDOMAIN", "demo").strip().lower()
    admin_name = os.getenv("SEED_ADMIN_NAME", "Demo Admin").strip()
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@demo.local").strip().lower()
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")

    return SeedConfig(
        db_url=db_url,
        sqlalchemy_url=sqlalchemy_url,
        docs_dir=docs_dir,
        urls=urls,
        use_ocr=use_ocr,
        ocr_lang=ocr_lang,
        org_name=org_name,
        org_subdomain=org_subdomain,
        admin_name=admin_name,
        admin_email=admin_email,
        admin_password=admin_password,
    )


def wait_for_database(max_attempts: int = 10, delay: float = 3.0) -> None:
    """Attempt to establish a database connection, retrying if necessary."""

    db_url = _build_database_url()
    safe_url = _safe_url(db_url)

    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(db_url, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
        except Exception as exc:  # pragma: no cover - depends on external DB
            logger.info(
                "Database not ready (attempt %d/%d): %s; retrying in %.1fs",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            if attempt >= max_attempts:
                raise RuntimeError("Database did not become ready in time") from exc
            time.sleep(delay)
            continue

        logger.info("Database connection established after %d attempt(s): %s", attempt, safe_url)
        return


def _run_schema_migrations(db_url: str) -> None:
    """Execute idempotent schema creation and migrations."""

    with psycopg.connect(db_url) as conn:
        ensure_schema(conn)
    logger.info("Schema ensured successfully.")


def _provision_tenant(factory: sessionmaker[Session], config: SeedConfig) -> uuid.UUID:
    """Create or reuse an organization and admin user for ingestion."""

    created_org = False
    created_user = False

    with factory() as session:
        org = session.execute(
            select(Organization).where(Organization.subdomain == config.org_subdomain)
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name=config.org_name, subdomain=config.org_subdomain)
            session.add(org)
            session.flush()
            created_org = True
            logger.info("Created organization %s (%s)", org.id, org.subdomain)
        else:
            logger.info("Organization %s already exists; reusing.", org.subdomain)

        user = session.execute(select(User).where(User.email == config.admin_email)).scalar_one_or_none()
        if user is None:
            password_hash = hash_password(config.admin_password)
            user = User(
                organization_id=org.id,
                email=config.admin_email.lower(),
                name=config.admin_name,
                password_hash=password_hash,
                role="admin",
            )
            session.add(user)
            session.flush()
            created_user = True
            logger.info("Created admin user %s", user.email)
        else:
            logger.info("Admin user %s already exists; reusing.", user.email)

        session.commit()

    if created_org and not created_user:
        logger.warning("Organization created but admin user reused; verify credentials manually.")
    if created_user and config.admin_password == "ChangeMe123!":
        logger.warning("Default admin password is in use; change it for production deployments.")

    return org.id


def _iter_documents(directory: Path) -> Iterable[Path]:
    """Yield files from ``directory`` matching supported ingestion extensions."""

    if directory.is_file():
        if directory.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield directory
        return

    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def _ingest_content(config: SeedConfig, tenant_id: uuid.UUID) -> None:
    """Ingest local documents and URLs for the provided tenant."""

    if config.docs_dir:
        docs = list(_iter_documents(config.docs_dir))
        if docs:
            for doc in docs:
                logger.info("Ingesting document %s", doc)
                job_id = ingestion_service.ingest_local(
                    doc,
                    tenant_id=tenant_id,
                    use_ocr=config.use_ocr,
                    ocr_lang=config.ocr_lang,
                )
                ingestion_service.wait_for_job(job_id)
        else:
            logger.info("No documents found under %s; skipping local ingestion.", config.docs_dir)
    else:
        logger.info("Document directory not configured; skipping local ingestion.")

    if config.urls:
        logger.info("Ingesting %d URL(s)", len(config.urls))
        job_id = ingestion_service.ingest_urls(config.urls, tenant_id=tenant_id)
        ingestion_service.wait_for_job(job_id)
    else:
        logger.info("No URLs configured for ingestion.")


def _resolve_repo_path(*parts: str) -> Path:
    """Return an absolute path under the repository root for ``parts``."""

    return Path(__file__).resolve().parent.joinpath(*parts)


def _ensure_sample_document(config: SeedConfig, tenant_id: uuid.UUID) -> None:
    """Ensure the bundled sample document exists for the tenant."""

    sample_path = _resolve_repo_path("sample_data", "example_document.pdf").resolve()
    if not sample_path.exists():
        logger.warning("Sample document %s not found; skipping ingestion.", sample_path)
        return

    with psycopg.connect(config.db_url) as conn:
        apply_tenant_settings(conn, tenant_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM documents WHERE tenant_id = %s AND path = %s LIMIT 1",
                (tenant_id, str(sample_path)),
            )
            exists = cur.fetchone() is not None

    if exists:
        logger.info(
            "Sample document already present for tenant %s: %s", tenant_id, sample_path
        )
        return

    job_id = ingestion_service.ingest_local(
        sample_path,
        tenant_id=tenant_id,
        use_ocr=config.use_ocr,
        ocr_lang=config.ocr_lang,
    )
    ingestion_service.wait_for_job(job_id)
    logger.info("Sample document ingested for tenant %s: %s", tenant_id, sample_path)


async def main() -> None:
    """Entrypoint for the seeding workflow."""

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    wait_for_database()

    config = _load_config()
    logger.info("Starting seed process using %s", _safe_url(config.db_url))

    os.environ.setdefault("DATABASE_URL", config.db_url)

    await asyncio.to_thread(_run_schema_migrations, config.db_url)

    session_factory = get_sessionmaker(database_url=config.sqlalchemy_url)
    tenant_id = await asyncio.to_thread(_provision_tenant, session_factory, config)

    logger.info("Tenant ready: %s", tenant_id)
    await asyncio.to_thread(_ingest_content, config, tenant_id)
    await asyncio.to_thread(_ensure_sample_document, config, tenant_id)

    logger.info("Seed process completed. Tenant ID: %s", tenant_id)


if __name__ == "__main__":
    asyncio.run(main())
