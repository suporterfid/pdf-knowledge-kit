import pathlib
import sys
import uuid
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI, Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.app_logging import init_logging
from app.models import Base, Organization, User
from app.security import create_access_token, hash_password, reset_jwt_settings_cache


@dataclass
class AuthContext:
    engine: object
    session_factory: sessionmaker[Session]
    organization_id: uuid.UUID
    users: dict[str, uuid.UUID]
    tokens: dict[str, str]
    password: str = "Secret123!"
    tenant_tokens: dict[uuid.UUID, dict[str, str]] = field(default_factory=dict)

    def token(self, role: str, tenant_id: uuid.UUID | None = None) -> str:
        if tenant_id is None or tenant_id == self.organization_id:
            return self.tokens[role]
        try:
            return self.tenant_tokens[tenant_id][role]
        except KeyError as exc:  # pragma: no cover - defensive guard for tests
            raise KeyError(f"Unknown tenant {tenant_id} for role {role}") from exc

    def header(self, role: str, tenant_id: uuid.UUID | None = None) -> dict[str, str]:
        token = self.token(role, tenant_id)
        return {"Authorization": f"Bearer {token}"}

    def create_tenant(self, name: str, subdomain: str) -> uuid.UUID:
        """Provision an additional tenant with users and JWT tokens for tests."""

        with self.session_factory.begin() as session:
            organization = Organization(name=name, subdomain=subdomain)
            session.add(organization)
            session.flush()

            user_tokens: dict[str, str] = {}
            for role in ("viewer", "operator", "admin"):
                user = User(
                    organization_id=organization.id,
                    email=f"{role}@{subdomain}.example",
                    name=f"{name} {role.title()}",
                    password_hash=hash_password(self.password),
                    role=role,
                )
                session.add(user)
                session.flush()
                token, _ = create_access_token(user)
                user_tokens[role] = token

        self.tenant_tokens[organization.id] = user_tokens
        return organization.id


@pytest.fixture
def app_factory(monkeypatch):
    def _create_app(log_dir: str, log_request_bodies: bool = False):
        """Create a FastAPI app with logging initialised."""
        monkeypatch.setenv("LOG_DIR", str(log_dir))
        if log_request_bodies:
            monkeypatch.setenv("LOG_REQUEST_BODIES", "true")
        app = FastAPI()

        @app.post("/echo")
        async def echo(request: Request):
            return await request.json()

        init_logging(app)
        return app

    return _create_app


@pytest.fixture
def tenant_auth(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> AuthContext:
    db_path = tmp_path_factory.mktemp("tenant-auth") / "auth.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TENANT_TOKEN_SECRET", "super-secret-key")
    monkeypatch.setenv("TENANT_TOKEN_AUDIENCE", "chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ISSUER", "auth.chatvolt")
    monkeypatch.setenv("TENANT_TOKEN_ALGORITHM", "HS256")
    reset_jwt_settings_cache()

    engine = create_engine(db_url, future=True)

    @event.listens_for(engine, "connect")
    def _register_uuid(conn, _record) -> None:  # pragma: no cover - SQLite test helper
        conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    users: dict[str, uuid.UUID] = {}
    user_objs: dict[str, User] = {}
    with session_factory.begin() as session:
        organization = Organization(name="Tenant", subdomain="tenant")
        session.add(organization)
        session.flush()
        for role in ("viewer", "operator", "admin"):
            user = User(
                organization_id=organization.id,
                email=f"{role}@tenant.example",
                name=role.title(),
                password_hash=hash_password("Secret123!"),
                role=role,
            )
            session.add(user)
            session.flush()
            users[role] = user.id
            user_objs[role] = user
        organization_id = organization.id

    tokens: dict[str, str] = {}
    for role, user in user_objs.items():
        token, _ = create_access_token(user)
        tokens[role] = token

    context = AuthContext(
        engine=engine,
        session_factory=session_factory,
        organization_id=organization_id,
        users=users,
        tokens=tokens,
    )
    context.tenant_tokens[organization_id] = tokens

    yield context

    Base.metadata.drop_all(engine)
    engine.dispose()
