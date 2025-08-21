import sys
import types
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

# Stub fastembed and prometheus instrumentator before importing application modules
class DummyEmbedder:
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


class DummyInstrumentator:
    def instrument(self, app):
        return self

    def expose(self, *args, **kwargs):
        return None


sys.modules['fastembed'] = types.SimpleNamespace(
    TextEmbedding=lambda model_name: DummyEmbedder()
)
sys.modules['prometheus_fastapi_instrumentator'] = types.SimpleNamespace(
    Instrumentator=lambda: DummyInstrumentator()
)

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from starlette.routing import Mount  # noqa: E402
from app.ingestion import service  # noqa: E402

# Remove static mount to make API routes available
app.router.routes = [r for r in app.router.routes if not (isinstance(r, Mount) and r.path == '')]


def _parse_events(resp):
    events = []
    current = None
    for line in resp.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode()
        if line.startswith("event:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current:
            events.append((current, line.split(":", 1)[1].strip()))
            current = None
    return events


@pytest.fixture
def pg_tmp(monkeypatch):
    try:
        import testing.postgresql
    except Exception:
        pytest.skip("testing.postgresql not installed")
    try:
        pg = testing.postgresql.Postgresql()
    except Exception:
        pytest.skip("PostgreSQL not available")
    dsn = pg.dsn()
    url = pg.url()
    # Configure environment variables for both ingestion and app
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("PGHOST", dsn["host"])
    monkeypatch.setenv("PGPORT", str(dsn["port"]))
    monkeypatch.setenv("PGDATABASE", dsn["database"])
    monkeypatch.setenv("PGUSER", dsn["user"])
    if dsn.get("password"):
        monkeypatch.setenv("PGPASSWORD", dsn["password"])
    yield pg
    pg.stop()


@pytest.fixture
def client():
    return TestClient(app)


def test_ingest_and_query_via_endpoints(pg_tmp, client, tmp_path):
    md_path = tmp_path / "sample.md"
    md_text = "Hello world\n\nThis is a test file."
    md_path.write_text(md_text, encoding="utf-8")

    job_id = service.ingest_local(md_path)
    future = service._runner.get(job_id)
    assert future is not None
    future.result(timeout=60)

    # Ask endpoint
    resp = client.post("/api/ask", json={"q": "Hello", "k": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert any("hello world" in s["content"].lower() for s in data["sources"])

    # Chat endpoint
    with client.stream("POST", "/api/chat", data={"q": "Hello", "k": "1", "sessionId": "s1"}) as resp2:
        events = _parse_events(resp2)
    sources_json = next(json.loads(d) for e, d in events if e == "sources")
    assert any("hello world" in s["content"].lower() for s in sources_json)
