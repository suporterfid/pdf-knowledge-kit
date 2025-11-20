import io
import pathlib
import sys
import types
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class DummyEmbedder:
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


# Stub fastembed before importing the app to avoid model downloads.
sys.modules["fastembed"] = types.SimpleNamespace(
    TextEmbedding=lambda model_name: DummyEmbedder()
)

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import CHAT_MAX_MESSAGE_LENGTH, SESSION_ID_MAX_LENGTH, app


def dummy_build_context(q, k, tenant_id=None):
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
    headers = {"X-Forwarded-For": "1.1.1.1", "X-Debug-Tenant": "tenant-1"}
    with patch("app.main.build_context", dummy_build_context):
        data = {"q": "hi", "k": "1", "sessionId": "s1"}
        with client.stream("POST", "/api/chat", data=data, headers=headers) as resp:
            events = _parse_events(resp)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)


def test_chat_with_pdf_attachment(client):
    headers = {"X-Forwarded-For": "1.1.1.2", "X-Debug-Tenant": "tenant-1"}
    files = {"files": ("test.pdf", _pdf_bytes(), "application/pdf")}
    data = {"q": "hi", "k": "1", "attachments": "[]", "sessionId": "s2"}
    with patch("app.main.build_context", dummy_build_context):
        with client.stream(
            "POST", "/api/chat", data=data, files=files, headers=headers
        ) as resp:
            events = _parse_events(resp)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)


def test_cancel_and_reconnect(client):
    headers = {"X-Forwarded-For": "1.1.1.3", "X-Debug-Tenant": "tenant-1"}
    with patch("app.main.build_context", dummy_build_context):
        with client.stream(
            "POST",
            "/api/chat",
            data={"q": "hi", "k": "1", "sessionId": "s3"},
            headers=headers,
        ) as resp:
            for _ in resp.iter_lines():
                break  # cancel early
        with client.stream(
            "POST",
            "/api/chat",
            data={"q": "again", "k": "1", "sessionId": "s3"},
            headers=headers,
        ) as resp2:
            events = _parse_events(resp2)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)


def test_invalid_mime_type(client):
    headers = {"X-Forwarded-For": "1.1.1.4", "X-Debug-Tenant": "tenant-1"}
    files = {"files": ("evil.txt", b"hello", "text/plain")}
    data = {"q": "hi", "k": "1", "attachments": "[]", "sessionId": "s4"}
    resp = client.post("/api/chat", data=data, files=files, headers=headers)
    assert resp.status_code == 400


def test_message_and_session_validation(client):
    headers = {"X-Forwarded-For": "1.1.1.5", "X-Debug-Tenant": "tenant-1"}
    long_msg = "a" * (CHAT_MAX_MESSAGE_LENGTH + 1)
    resp_msg = client.post(
        "/api/chat",
        data={"q": long_msg, "k": "1", "sessionId": "s5"},
        headers=headers,
    )
    assert resp_msg.status_code == 400
    long_session = "s" * (SESSION_ID_MAX_LENGTH + 1)
    resp_sess = client.post(
        "/api/chat",
        data={"q": "hi", "k": "1", "sessionId": long_session},
        headers=headers,
    )
    assert resp_sess.status_code == 400


def test_rate_limit(client):
    headers = {"X-Forwarded-For": "2.2.2.2", "X-Debug-Tenant": "tenant-1"}
    data = {"q": "hi", "k": "1", "sessionId": "rl"}
    with patch("app.main.build_context", dummy_build_context):
        for _ in range(5):
            resp_ok = client.post("/api/chat", data=data, headers=headers)
            assert resp_ok.status_code == 200
        resp = client.post("/api/chat", data=data, headers=headers)
    assert resp.status_code == 429


def test_chat_with_llm_prompt(client, monkeypatch):
    headers = {"X-Forwarded-For": "3.3.3.3", "X-Debug-Tenant": "tenant-1"}

    class DummyStream:
        def __iter__(self):
            yield types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(delta=types.SimpleNamespace(content="hi"))
                ],
                usage=None,
            )
            yield types.SimpleNamespace(
                choices=[],
                usage=types.SimpleNamespace(
                    prompt_tokens=1, completion_tokens=1, total_tokens=2
                ),
            )

    class DummyClient:
        def __init__(self):
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self.create)
            )
            self.messages = None

        def create(self, **kwargs):
            self.messages = kwargs.get("messages")
            return DummyStream()

    dummy_client = DummyClient()
    monkeypatch.delenv("OPENAI_LANG", raising=False)
    with (
        patch("app.main.build_context", dummy_build_context),
        patch("app.main.client", dummy_client),
        patch("app.main.detect", lambda _: "en"),
    ):
        data = {"q": "hi", "k": "1", "sessionId": "sllm"}
        with client.stream("POST", "/api/chat", data=data, headers=headers) as resp:
            events = _parse_events(resp)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)
    assert (
        dummy_client.messages[0]["content"]
        == "Answer the user's question using the supplied context. Reply in en."
    )


def test_chat_with_custom_system_prompt(client, monkeypatch):
    headers = {"X-Forwarded-For": "3.3.3.4", "X-Debug-Tenant": "tenant-1"}

    class DummyStream:
        def __iter__(self):
            yield types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(delta=types.SimpleNamespace(content="hi"))
                ],
                usage=None,
            )
            yield types.SimpleNamespace(
                choices=[],
                usage=types.SimpleNamespace(
                    prompt_tokens=1, completion_tokens=1, total_tokens=2
                ),
            )

    class DummyClient:
        def __init__(self):
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self.create)
            )
            self.messages = None

        def create(self, **kwargs):
            self.messages = kwargs.get("messages")
            return DummyStream()

    dummy_client = DummyClient()
    monkeypatch.delenv("OPENAI_LANG", raising=False)
    monkeypatch.setenv("SYSTEM_PROMPT", "You are a helper.")
    with (
        patch("app.main.build_context", dummy_build_context),
        patch("app.main.client", dummy_client),
        patch("app.main.detect", lambda _: "en"),
    ):
        data = {"q": "hi", "k": "1", "sessionId": "sllm2"}
        with client.stream("POST", "/api/chat", data=data, headers=headers) as resp:
            events = _parse_events(resp)
    assert any(e[0] == "token" for e in events)
    assert any(e[0] == "done" for e in events)
    assert (
        dummy_client.messages[0]["content"]
        == "You are a helper. Answer the user's question using the supplied context. Reply in en."
    )
