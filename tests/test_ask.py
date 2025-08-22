import sys
import types
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class DummyEmbedder:
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


# Stub fastembed before importing the app to avoid model downloads.
sys.modules['fastembed'] = types.SimpleNamespace(
    TextEmbedding=lambda model_name: DummyEmbedder()
)
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import app
from starlette.routing import Mount

# Remove static mount to access API routes during tests
app.router.routes = [r for r in app.router.routes if not (isinstance(r, Mount) and r.path == '')]


@pytest.fixture
def client():
    return TestClient(app)


def dummy_build_context(q, k):
    return "context", [
        {"path": "doc.pdf", "chunk_index": 0, "content": "context", "distance": 0.0}
    ]


def test_ask_without_llm(client):
    with patch("app.main.build_context", dummy_build_context), patch("app.main.client", None):
        resp = client.post("/api/ask", json={"q": "hi", "k": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "context"
    assert data["used_llm"] is False
    assert data["sources"]


def test_ask_with_llm(client):
    class DummyCompletion:
        def __init__(self):
            self.choices = [types.SimpleNamespace(message={"content": "llm"})]

    class DummyClient:
        def __init__(self):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))
            self.messages = None

        def create(self, **kwargs):
            self.messages = kwargs.get("messages")
            return DummyCompletion()

    dummy_client = DummyClient()
    with patch("app.main.build_context", dummy_build_context), patch("app.main.client", dummy_client), patch("app.main.detect", lambda _: "en"):
        resp = client.post("/api/ask", json={"q": "hi", "k": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "llm"
    assert data["used_llm"] is True
    assert data["sources"]
    assert dummy_client.messages[0]["content"] == "Answer the user's question using the supplied context. Reply in en."
