from __future__ import annotations

import logging

from app.models import Base
from app.models.session import get_engine
from app.security import verify_password
from sqlalchemy.orm import sessionmaker
from tools import bootstrap_demo


def _session_factory() -> sessionmaker:
    engine = get_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_ensure_demo_entities_creates_records(caplog):
    factory = _session_factory()
    caplog.set_level(logging.INFO, logger="tools.bootstrap_demo")

    with factory() as session:
        org, user, created_org, created_user = bootstrap_demo.ensure_demo_entities(
            session,
            organization_name="Demo Org",
            organization_subdomain="demo",
            user_name="Demo User",
            user_email="testuser@example.com",
            user_password="password",
            user_role="admin",
        )
        session.commit()

    assert created_org is True
    assert created_user is True
    assert org.subdomain == "demo"
    assert user.email == "testuser@example.com"
    assert verify_password("password", user.password_hash)

    messages = [record.message for record in caplog.records if record.name == "tools.bootstrap_demo"]
    assert any("Created organization" in message for message in messages)
    assert any("Created user" in message for message in messages)


def test_ensure_demo_entities_reuses_existing(caplog):
    factory = _session_factory()

    with factory() as session:
        org, user, _, _ = bootstrap_demo.ensure_demo_entities(session)
        session.commit()
        existing_org_id = org.id
        existing_user_id = user.id
        existing_hash = user.password_hash

    caplog.set_level(logging.INFO, logger="tools.bootstrap_demo")
    caplog.clear()

    with factory() as session:
        org2, user2, created_org, created_user = bootstrap_demo.ensure_demo_entities(session)
        session.commit()

    assert created_org is False
    assert created_user is False
    assert org2.id == existing_org_id
    assert user2.id == existing_user_id
    assert user2.password_hash == existing_hash

    messages = [record.message for record in caplog.records if record.name == "tools.bootstrap_demo"]
    assert any("already exists" in message for message in messages)
