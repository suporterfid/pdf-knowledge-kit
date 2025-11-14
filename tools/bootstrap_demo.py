"""Utility CLI to bootstrap a demo organization and admin user."""

from __future__ import annotations

import logging
import os

import psycopg
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.ingestion.service import ensure_schema
from app.models import Organization, User
from app.models.session import get_sessionmaker
from app.security import hash_password

logger = logging.getLogger("tools.bootstrap_demo")

DEFAULT_ORG_NAME = "Demo Organization"
DEFAULT_ORG_SUBDOMAIN = "demo"
DEFAULT_USER_NAME = "Demo User"
DEFAULT_USER_EMAIL = "testuser@example.com"
DEFAULT_USER_PASSWORD = "password"
DEFAULT_USER_ROLE = "admin"


def _as_sqlalchemy_url(db_url: str) -> str:
    """Return a SQLAlchemy URL that uses the ``psycopg`` driver."""

    if db_url.startswith("postgresql+psycopg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return db_url


def _safe_url(db_url: str) -> str:
    """Return ``db_url`` with any password redacted for logging."""

    try:
        parsed = make_url(db_url)
    except Exception:  # pragma: no cover - defensive fallback
        return db_url
    if parsed.password is None:
        return db_url
    redacted = parsed.set(password="***")
    return redacted.render_as_string(hide_password=False)


def ensure_demo_entities(
    session: Session,
    *,
    organization_name: str = DEFAULT_ORG_NAME,
    organization_subdomain: str = DEFAULT_ORG_SUBDOMAIN,
    user_name: str = DEFAULT_USER_NAME,
    user_email: str = DEFAULT_USER_EMAIL,
    user_password: str = DEFAULT_USER_PASSWORD,
    user_role: str = DEFAULT_USER_ROLE,
) -> tuple[Organization, User, bool, bool]:
    """Ensure demo organization and user exist in ``session``.

    Args:
        session: Active SQLAlchemy session.
        organization_name: Name to assign when creating the organization.
        organization_subdomain: Unique subdomain for lookup/creation.
        user_name: Display name for the demo user.
        user_email: Login e-mail used to locate or create the user.
        user_password: Raw password to hash when creating the user.
        user_role: Role assigned to the demo user (e.g., ``admin``).

    Returns:
        Tuple containing the organization, the user, and two booleans
        indicating whether the organization and user were created.
    """

    normalized_subdomain = organization_subdomain.strip().lower()
    normalized_email = user_email.strip().lower()

    created_org = False
    created_user = False

    org = (
        session.execute(
            select(Organization).where(Organization.subdomain == normalized_subdomain)
        )
        .scalar_one_or_none()
    )
    if org is None:
        org = Organization(name=organization_name.strip(), subdomain=normalized_subdomain)
        session.add(org)
        session.flush()
        created_org = True
        logger.info("Created organization %s (id=%s)", org.subdomain, org.id)
    else:
        logger.info(
            "Organization %s already exists (id=%s)", org.subdomain, org.id
        )

    user = (
        session.execute(select(User).where(User.email == normalized_email))
        .scalar_one_or_none()
    )
    if user is None:
        password_hash = hash_password(user_password)
        user = User(
            organization_id=org.id,
            email=normalized_email,
            name=user_name.strip(),
            password_hash=password_hash,
            role=user_role,
        )
        session.add(user)
        session.flush()
        created_user = True
        logger.info("Created user %s (id=%s)", user.email, user.id)
    else:
        logger.info("User %s already exists (id=%s)", user.email, user.id)

    return org, user, created_org, created_user


def main() -> None:
    """Script entrypoint for ensuring the demo organization and user exist."""

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    safe_db_url = _safe_url(db_url)
    logger.info("Ensuring schema on %s", safe_db_url)

    with psycopg.connect(db_url) as conn:
        ensure_schema(conn)

    sqlalchemy_url = _as_sqlalchemy_url(db_url)
    SessionLocal = get_sessionmaker(database_url=sqlalchemy_url)

    with SessionLocal() as session:
        org, user, created_org, created_user = ensure_demo_entities(session)
        session.commit()

    logger.info(
        "Organization %s (%s)",
        "created" if created_org else "existing",
        org.subdomain,
    )
    logger.info(
        "User %s (%s)",
        "created" if created_user else "existing",
        user.email,
    )


if __name__ == "__main__":  # pragma: no cover - CLI execution
    main()
