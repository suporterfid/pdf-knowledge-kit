import io
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


def dummy_build_context(q, k):
    return "context", [
        {"path": "doc.pdf", "chunk_index": 0, "content": "context", "distance": 0.0}
    ]


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


def _pdf_bytes():
    from pypdf import PdfWriter

    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_without_attachment(client):
    with patch("app.main.build_context", dummy_build_context):
        with client.stream("POST", "/api/chat", data={"q": "hi", "k": "1"}) as resp:
            events = _parse_events(resp)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)


def test_chat_with_pdf_attachment(client):
    files = {"files": ("test.pdf", _pdf_bytes(), "application/pdf")}
    data = {"q": "hi", "k": "1", "attachments": "[]"}
    with patch("app.main.build_context", dummy_build_context):
        with client.stream("POST", "/api/chat", data=data, files=files) as resp:
            events = _parse_events(resp)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)


def test_cancel_and_reconnect(client):
    with patch("app.main.build_context", dummy_build_context):
        with client.stream("POST", "/api/chat", data={"q": "hi", "k": "1"}) as resp:
            for _ in resp.iter_lines():
                break  # cancel early
        with client.stream("POST", "/api/chat", data={"q": "again", "k": "1"}) as resp2:
            events = _parse_events(resp2)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)

