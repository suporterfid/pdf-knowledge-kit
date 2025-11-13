"""Unit tests for main.py endpoints and helper functions.

This module provides comprehensive test coverage for endpoints in app/main.py
that were previously untested, including:
- /api/health
- /api/version
- /api/config
- /api/upload
- /api/chat (GET variant)

It also tests helper functions like get_client_ip, remove_file_after_ttl,
and _answer_with_context.
"""

import asyncio
import io
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient


class DummyEmbedder:
    """Mock embedder to avoid downloading models during tests."""
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


# Stub fastembed before importing the app to avoid model downloads.
sys.modules['fastembed'] = types.SimpleNamespace(
    TextEmbedding=lambda model_name: DummyEmbedder()
)
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import (
    app,
    get_client_ip,
    remove_file_after_ttl,
    _answer_with_context,
    UPLOAD_MAX_SIZE,
    UPLOAD_MAX_FILES,
    CHAT_MAX_MESSAGE_LENGTH,
    SESSION_ID_MAX_LENGTH,
)
from app.__version__ import __version__, __build_date__, __commit_sha__


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_returns_ok_status(self, client):
        """Test that health endpoint returns status ok."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_returns_json(self, client):
        """Test that health endpoint returns JSON content type."""
        resp = client.get("/api/health")
        assert "application/json" in resp.headers.get("content-type", "")


class TestVersionEndpoint:
    """Tests for /api/version endpoint."""

    def test_version_returns_version_info(self, client):
        """Test that version endpoint returns version information."""
        resp = client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "build_date" in data
        assert "commit_sha" in data

    def test_version_matches_package_version(self, client):
        """Test that version endpoint returns correct version from package."""
        resp = client.get("/api/version")
        data = resp.json()
        assert data["version"] == __version__
        assert data["build_date"] == __build_date__
        assert data["commit_sha"] == __commit_sha__


class TestConfigEndpoint:
    """Tests for /api/config endpoint."""

    def test_config_returns_default_values(self, client):
        """Test that config endpoint returns default configuration."""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["BRAND_NAME"] == "PDF Knowledge Kit"
        assert data["POWERED_BY_LABEL"] == "Powered by PDF Knowledge Kit"
        assert data["LOGO_URL"] == ""
        assert data["UPLOAD_MAX_SIZE"] == UPLOAD_MAX_SIZE
        assert data["UPLOAD_MAX_FILES"] == UPLOAD_MAX_FILES

    def test_config_respects_environment_variables(self, client, monkeypatch):
        """Test that config endpoint uses environment variables when set."""
        monkeypatch.setenv("BRAND_NAME", "Test Brand")
        monkeypatch.setenv("POWERED_BY_LABEL", "Test Label")
        monkeypatch.setenv("LOGO_URL", "https://example.com/logo.png")
        
        # Re-import to pick up new env vars
        from importlib import reload
        import app.main
        reload(app.main)
        test_client = TestClient(app.main.app)
        
        resp = test_client.get("/api/config")
        data = resp.json()
        assert data["BRAND_NAME"] == "Test Brand"
        assert data["POWERED_BY_LABEL"] == "Test Label"
        assert data["LOGO_URL"] == "https://example.com/logo.png"


class TestUploadEndpoint:
    """Tests for /api/upload endpoint."""

    def _create_simple_pdf(self):
        """Create a simple PDF file for testing."""
        from pypdf import PdfWriter
        buf = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(buf)
        return buf.getvalue()

    def test_upload_valid_pdf(self, client):
        """Test uploading a valid PDF file."""
        pdf_bytes = self._create_simple_pdf()
        files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
        
        # Mock background task to avoid blocking
        with patch("app.main.BackgroundTasks.add_task"):
            resp = client.post("/api/upload", files=files)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert data["url"].startswith("/uploads/")
        assert data["url"].endswith("-test.pdf")

    def test_upload_invalid_mime_type(self, client):
        """Test that non-PDF files are rejected."""
        files = {"file": ("test.txt", b"hello", "text/plain")}
        resp = client.post("/api/upload", files=files)
        assert resp.status_code == 400
        assert "Invalid file type" in resp.json()["detail"]

    def test_upload_file_too_large(self, client):
        """Test that files exceeding max size are rejected."""
        # Create a file slightly larger than UPLOAD_MAX_SIZE
        large_bytes = b'x' * (UPLOAD_MAX_SIZE + 1000)
        files = {"file": ("large.pdf", large_bytes, "application/pdf")}
        resp = client.post("/api/upload", files=files)
        assert resp.status_code == 400
        assert "File too large" in resp.json()["detail"]

    def test_upload_creates_file_with_uuid(self, client):
        """Test that uploaded file is saved with UUID prefix."""
        pdf_bytes = self._create_simple_pdf()
        files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
        
        # Mock background task to avoid blocking
        with patch("app.main.BackgroundTasks.add_task"):
            resp = client.post("/api/upload", files=files)
        
        data = resp.json()
        url = data["url"]
        # URL should have format /uploads/{uuid}-test.pdf
        filename = url.split("/")[-1]
        assert "-test.pdf" in filename
        # UUID part should be 32 hex characters
        uuid_part = filename.split("-")[0]
        assert len(uuid_part) == 32
        assert all(c in "0123456789abcdef" for c in uuid_part)


class TestChatGetEndpoint:
    """Tests for /api/chat GET variant."""

    def dummy_build_context(self, q, k):
        return "context", [
            {"path": "doc.pdf", "chunk_index": 0, "content": "context", "distance": 0.0}
        ]

    def test_chat_get_basic_query(self, client):
        """Test GET chat endpoint with basic query."""
        headers = {"X-Forwarded-For": "10.0.0.1"}
        with patch("app.main.build_context", self.dummy_build_context):
            with client.stream("GET", "/api/chat?q=hello&k=1&sessionId=test", headers=headers) as resp:
                assert resp.status_code == 200
                # Read at least one event
                found_event = False
                for line in resp.iter_lines():
                    if line:
                        found_event = True
                        break
                assert found_event

    def test_chat_get_without_session_id(self, client):
        """Test GET chat endpoint without sessionId (optional)."""
        headers = {"X-Forwarded-For": "10.0.0.2"}
        with patch("app.main.build_context", self.dummy_build_context):
            with client.stream("GET", "/api/chat?q=hello&k=1", headers=headers) as resp:
                assert resp.status_code == 200

    def test_chat_get_message_too_long(self, client):
        """Test GET chat endpoint rejects messages that are too long."""
        headers = {"X-Forwarded-For": "10.0.0.3"}
        long_msg = "a" * (CHAT_MAX_MESSAGE_LENGTH + 1)
        resp = client.get(f"/api/chat?q={long_msg}&k=1", headers=headers)
        assert resp.status_code == 400
        assert "Message too long" in resp.json()["detail"]

    def test_chat_get_session_id_too_long(self, client):
        """Test GET chat endpoint rejects invalid sessionId."""
        headers = {"X-Forwarded-For": "10.0.0.4"}
        long_session = "s" * (SESSION_ID_MAX_LENGTH + 1)
        resp = client.get(f"/api/chat?q=hello&sessionId={long_session}", headers=headers)
        assert resp.status_code == 400
        assert "Invalid sessionId" in resp.json()["detail"]


class TestGetClientIpFunction:
    """Tests for get_client_ip helper function."""

    def test_get_client_ip_from_forwarded_header(self):
        """Test extracting IP from X-Forwarded-For header."""
        # Create a mock request with X-Forwarded-For header
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "192.168.1.1, 10.0.0.1"
        mock_request.client.host = "127.0.0.1"
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_from_client_host(self):
        """Test extracting IP from client host when no X-Forwarded-For."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.client.host = "127.0.0.1"
        
        ip = get_client_ip(mock_request)
        assert ip == "127.0.0.1"

    def test_get_client_ip_strips_whitespace(self):
        """Test that extracted IP has whitespace stripped."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "  192.168.1.1  , 10.0.0.1"
        mock_request.client.host = "127.0.0.1"
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.1"


class TestRemoveFileAfterTtlFunction:
    """Tests for remove_file_after_ttl helper function."""

    def test_remove_file_after_ttl_deletes_file(self):
        """Test that file is deleted after TTL expires."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"test content")
        
        assert os.path.exists(tmp_path)
        
        # Remove after 0.1 seconds (run in event loop)
        asyncio.run(remove_file_after_ttl(tmp_path, 0.1))
        
        # File should be deleted
        assert not os.path.exists(tmp_path)

    def test_remove_file_after_ttl_handles_missing_file(self):
        """Test that function handles already-deleted files gracefully."""
        non_existent = "/tmp/non_existent_file_12345.txt"
        # Should not raise an exception
        asyncio.run(remove_file_after_ttl(non_existent, 0.1))


class TestAnswerWithContextFunction:
    """Tests for _answer_with_context helper function."""

    def test_answer_without_llm_returns_context(self):
        """Test that without LLM, the function returns the context."""
        with patch("app.main.client", None):
            answer, used_llm = _answer_with_context("What is AI?", "AI is artificial intelligence.")
            assert answer == "AI is artificial intelligence."
            assert used_llm is False

    def test_answer_without_context_returns_echo(self):
        """Test that without context and without LLM, question is echoed."""
        with patch("app.main.client", None):
            answer, used_llm = _answer_with_context("What is AI?", "")
            assert "What is AI?" in answer
            assert used_llm is False

    def test_answer_with_llm_uses_openai(self):
        """Test that with LLM configured, it uses OpenAI."""
        class DummyCompletion:
            def __init__(self):
                self.choices = [types.SimpleNamespace(message={"content": "AI is intelligence exhibited by machines."})]

        class DummyClient:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

            def create(self, **kwargs):
                return DummyCompletion()

        with patch("app.main.client", DummyClient()), patch("app.main.detect", lambda _: "en"):
            answer, used_llm = _answer_with_context("What is AI?", "AI is artificial intelligence.")
            assert answer == "AI is intelligence exhibited by machines."
            assert used_llm is True

    def test_answer_with_llm_fallback_on_error(self):
        """Test that LLM errors fall back to deterministic response."""
        class DummyClient:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

            def create(self, **kwargs):
                raise Exception("API Error")

        with patch("app.main.client", DummyClient()), patch("app.main.detect", lambda _: "en"):
            answer, used_llm = _answer_with_context("What is AI?", "AI is artificial intelligence.")
            assert answer == "AI is artificial intelligence."
            assert used_llm is False

    def test_answer_respects_language_env_var(self, monkeypatch):
        """Test that OPENAI_LANG environment variable is respected."""
        class DummyCompletion:
            def __init__(self):
                self.choices = [types.SimpleNamespace(message={"content": "Response"})]

        class DummyClient:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))
                self.system_prompt = None

            def create(self, **kwargs):
                self.system_prompt = kwargs["messages"][0]["content"]
                return DummyCompletion()

        dummy_client = DummyClient()
        monkeypatch.setenv("OPENAI_LANG", "pt")
        with patch("app.main.client", dummy_client):
            answer, used_llm = _answer_with_context("Pergunta", "Contexto")
            assert "Reply in pt" in dummy_client.system_prompt
            assert used_llm is True

    def test_answer_detects_language_when_no_env_var(self):
        """Test that language is detected when OPENAI_LANG is not set."""
        class DummyCompletion:
            def __init__(self):
                self.choices = [types.SimpleNamespace(message={"content": "Response"})]

        class DummyClient:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))
                self.system_prompt = None

            def create(self, **kwargs):
                self.system_prompt = kwargs["messages"][0]["content"]
                return DummyCompletion()

        dummy_client = DummyClient()
        with patch("app.main.client", dummy_client), patch("app.main.detect", lambda _: "fr"):
            answer, used_llm = _answer_with_context("Question", "Context")
            assert "Reply in fr" in dummy_client.system_prompt
            assert used_llm is True
