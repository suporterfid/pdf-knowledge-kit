import logging
from logging.handlers import TimedRotatingFileHandler

from fastapi import FastAPI

from app.app_logging import init_logging


def _clear_handlers(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    return logger


def test_init_logging_adds_handlers(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    app_logger = _clear_handlers("app")
    access_logger = _clear_handlers("uvicorn.access")

    app = FastAPI()
    init_logging(app)

    assert any(
        isinstance(h, TimedRotatingFileHandler) for h in app_logger.handlers
    )
    assert any(
        isinstance(h, TimedRotatingFileHandler) for h in access_logger.handlers
    )

    app_logger.handlers.clear()
    access_logger.handlers.clear()


def test_init_logging_preserves_existing_access_handlers(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    access_logger = _clear_handlers("uvicorn.access")

    stream_handler = logging.StreamHandler()
    access_logger.addHandler(stream_handler)

    init_logging()

    assert access_logger.handlers == [stream_handler]
    access_logger.handlers.clear()
