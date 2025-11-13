from __future__ import annotations

import uuid

import pytest

pytest.importorskip("sqlalchemy")
from app.models import Base, Organization, User
from sqlalchemy import create_engine  # type: ignore  # noqa: E402
from sqlalchemy.exc import IntegrityError  # type: ignore  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # type: ignore  # noqa: E402


@pytest.fixture
def engine():
    return create_engine("sqlite+pysqlite:///:memory:", future=True)


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as session:
        yield session
        session.rollback()
    Base.metadata.drop_all(engine)


def test_can_persist_organization_and_user(session: Session) -> None:
    organization = Organization(
        id=uuid.uuid4(),
        name="Acme Inc.",
        subdomain="acme",
    )
    session.add(organization)
    session.flush()

    user = User(
        id=uuid.uuid4(),
        organization_id=organization.id,
        email="owner@acme.com",
        password_hash="hashed",
        name="Owner",
    )
    session.add(user)
    session.flush()

    assert organization.plan_type == "free"
    assert user.organization_id == organization.id
    assert user.organization is organization
    assert organization.users == [user]
    assert user.role == "viewer"


def test_unique_subdomain_constraint(session: Session) -> None:
    session.add(
        Organization(
            id=uuid.uuid4(),
            name="First",
            subdomain="tenant",
        )
    )
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(
            Organization(
                id=uuid.uuid4(),
                name="Second",
                subdomain="tenant",
            )
        )
        session.commit()
    session.rollback()


def test_unique_email_constraint(session: Session) -> None:
    org = Organization(id=uuid.uuid4(), name="Org", subdomain="org")
    session.add(org)
    session.flush()

    session.add(
        User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email="member@org.com",
            password_hash="hash",
            name="Member",
        )
    )
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(
            User(
                id=uuid.uuid4(),
                organization_id=org.id,
                email="member@org.com",
                password_hash="hash2",
                name="Member Two",
            )
        )
        session.commit()
    session.rollback()
