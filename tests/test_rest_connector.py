from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from app.ingestion.connectors.rest import RestConnector
from app.ingestion.models import Source, SourceType
from app.ingestion.parsers import Chunk


class _FakeResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError("unexpected HTTP status")

    def json(self) -> Dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, responses: List[_FakeResponse]):
        self._responses = responses
        self.requests: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("no more responses queued")
        return self._responses.pop(0)


@pytest.fixture()
def fake_chunk(monkeypatch):
    captured: List[Dict[str, Any]] = []

    def _chunk(text: str, **kwargs: Any):
        extra = kwargs.get("extra_metadata") or {}
        captured.append({"text": text, **kwargs})
        return [
            Chunk(
                content=text,
                source_path=kwargs["source_path"],
                mime_type=kwargs["mime_type"],
                page_number=kwargs.get("page_number"),
                extra=extra,
            )
        ]

    monkeypatch.setattr("app.ingestion.connectors.rest.chunk_text", _chunk)
    return captured


def _make_source(**overrides: Any) -> Source:
    payload = {
        "id": uuid4(),
        "type": SourceType.API,
        "created_at": datetime.utcnow(),
        "params": {
            "base_url": "https://api.example.com",
            "endpoint": "/messages",
            "headers": {"Authorization": "Bearer {token}"},
            "records_path": "data",
            "id_field": "id",
            "text_fields": ["content"],
            "timestamp_field": "timestamp",
            "pagination": {"type": "cursor", "cursor_param": "cursor", "next_cursor_path": "next"},
        },
        "credentials": {"token": "secret-token"},
    }
    payload.update(overrides)
    return Source(**payload)


def test_rest_connector_cursor_pagination(monkeypatch, fake_chunk):
    responses = [
        _FakeResponse({
            "data": [
                {"id": 1, "content": "First", "timestamp": "2024-01-01T00:00:00Z"},
            ],
            "next": "cursor-2",
        }),
        _FakeResponse({
            "data": [
                {"id": 2, "content": "Second", "timestamp": "2024-01-01T00:01:00Z"},
            ],
            "next": None,
        }),
    ]
    session = _FakeSession(responses)
    source = _make_source()

    connector = RestConnector(source, session=session)
    records = list(connector.stream())

    assert len(records) == 2
    assert connector.job_metadata == {"pages": 2, "records": 2, "chunks": 2}
    assert connector.next_sync_state.get("cursor") is None

    # Headers should have been formatted using credentials
    assert session.requests[0]["headers"]["Authorization"] == "Bearer secret-token"

    first_chunk = fake_chunk[0]
    assert first_chunk["extra_metadata"] == {
        "connector": "rest",
        "endpoint": "https://api.example.com/messages",
        "record_id": 1,
        "timestamp": "2024-01-01T00:00:00Z",
    }
    assert records[0].document_path.endswith("messages/1")
    assert records[0].document_sync_state == {"record_id": 1, "timestamp": "2024-01-01T00:00:00Z"}


def test_rest_connector_page_pagination(monkeypatch, fake_chunk):
    responses = [
        _FakeResponse({
            "results": [
                {"id": "a", "content": "Alpha"},
                {"id": "b", "content": "Beta"},
            ]
        }),
        _FakeResponse({
            "results": [
                {"id": "c", "content": "Gamma"},
            ]
        }),
    ]
    session = _FakeSession(responses)
    source = _make_source(
        params={
            "base_url": "https://api.example.com",
            "endpoint": "/items",
            "records_path": "results",
            "id_field": "id",
            "text_fields": ["content"],
            "pagination": {
                "type": "page",
                "page_param": "page",
                "page_size_param": "size",
                "page_size": 2,
                "start_page": 1,
            },
        }
    )

    connector = RestConnector(source, session=session)
    list(connector.stream())

    assert connector.job_metadata == {"pages": 2, "records": 3, "chunks": 3}
    assert connector.next_sync_state.get("page") == 3

    # Ensure page parameters increment across requests
    first_request = session.requests[0]
    second_request = session.requests[1]
    assert first_request["params"]["page"] == 1
    assert first_request["params"]["size"] == 2
    assert second_request["params"]["page"] == 2
