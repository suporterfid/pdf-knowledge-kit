import json
import logging
import tempfile
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

import pytest
from starlette.testclient import TestClient

from app.app_logging import init_logging


def _clear_handlers(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    return logger


@pytest.fixture
def log_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("LOG_DIR", tmpdir)
        yield Path(tmpdir)


def test_timed_rotating_handler_configuration(log_dir, monkeypatch):
    monkeypatch.setenv("LOG_RETENTION_DAYS", "5")
    app_logger = _clear_handlers("app")
    access_logger = _clear_handlers("uvicorn.access")

    init_logging()

    app_handler = next(
        h for h in app_logger.handlers if isinstance(h, TimedRotatingFileHandler)
    )
    assert app_handler.when == "MIDNIGHT"
    assert app_handler.backupCount == 5

    access_handler = next(
        h for h in access_logger.handlers if isinstance(h, TimedRotatingFileHandler)
    )
    assert access_handler.when == "MIDNIGHT"
    assert access_handler.backupCount == 5

    app_logger.handlers.clear()
    access_logger.handlers.clear()


def test_log_files_and_redaction(log_dir, app_factory):
    _clear_handlers("app")
    _clear_handlers("uvicorn.access")
    app = app_factory(log_dir, log_request_bodies=True)

    app_logger = logging.getLogger("app")
    app_logger.info("hello app")

    with TestClient(app) as client:
        resp = client.post(
            "/echo",
            json={"token": "secret", "value": 1},
            headers={"Authorization": "Bearer secret"},
        )
        assert resp.status_code == 200

    for logger in (app_logger, logging.getLogger("uvicorn.access")):
        for handler in logger.handlers:
            handler.flush()

    app_log = log_dir / "app.log"
    access_log = log_dir / "access.log"

    assert app_log.exists() and app_log.read_text().strip()
    assert "hello app" in app_log.read_text()

    assert access_log.exists() and access_log.read_text().strip()
    access_line = access_log.read_text().splitlines()[-1]
    payload = access_line.split(": ", 1)[1]
    data = json.loads(payload)
    assert data["headers"]["authorization"] == "***"
    assert data["body"]["token"] == "***"

    app_logger.handlers.clear()
    logging.getLogger("uvicorn.access").handlers.clear()
