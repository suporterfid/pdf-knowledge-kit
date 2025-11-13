import json
import logging
import pathlib
import sys

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.app_logging import _install_access_logging


def _create_app() -> FastAPI:
    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request):
        return {"rid": request.state.request_id}

    @app.get("/api/health")
    async def health():  # pragma: no cover - simple
        return {"status": "ok"}

    _install_access_logging(app)
    return app


def test_access_logging_request_id_and_scrubbing(caplog, monkeypatch):
    monkeypatch.setenv("LOG_REQUEST_BODIES", "true")
    app = _create_app()

    with (
        TestClient(app) as client,
        caplog.at_level(logging.INFO, logger="uvicorn.access"),
    ):
        resp = client.post(
            "/echo",
            json={"token": "secret", "a": 1},
            headers={"X-Request-Id": "abc", "Authorization": "Bearer secret"},
        )

        assert resp.status_code == 200
        assert resp.headers["X-Request-Id"] == "abc"
        assert resp.json() == {"rid": "abc"}

        record = caplog.records[0]
        data = json.loads(record.getMessage())
        assert data["request_id"] == "abc"
        assert data["headers"]["authorization"] == "***"
        assert data["body"]["token"] == "***"

        caplog.clear()
        client.get("/api/health")
        assert len(caplog.records) == 0
