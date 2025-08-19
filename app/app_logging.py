from __future__ import annotations

import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from fastapi import FastAPI


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - simple
        log_record = {
            "level": record.levelname,
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def _get_formatter(log_json: bool) -> logging.Formatter:
    if log_json:
        return JsonFormatter()
    return logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s")


def init_logging(app: FastAPI | None = None) -> None:
    """Initialise application and access loggers."""

    log_dir = os.getenv("LOG_DIR", "logs")
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_json = os.getenv("LOG_JSON", "false").lower() == "true"
    retention_days = int(os.getenv("LOG_RETENTION_DAYS", "7"))
    rotate_utc = os.getenv("LOG_ROTATE_UTC", "false").lower() == "true"

    os.makedirs(log_dir, exist_ok=True)

    formatter = _get_formatter(log_json)
    log_level = getattr(logging, log_level_str, logging.INFO)

    app_logger = logging.getLogger("app")
    if not app_logger.handlers:
        handler = TimedRotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            when="midnight",
            backupCount=retention_days,
            utc=rotate_utc,
        )
        handler.setFormatter(formatter)
        app_logger.addHandler(handler)
    app_logger.setLevel(log_level)

    access_logger = logging.getLogger("uvicorn.access")
    if not access_logger.handlers:
        handler = TimedRotatingFileHandler(
            os.path.join(log_dir, "access.log"),
            when="midnight",
            backupCount=retention_days,
            utc=rotate_utc,
        )
        handler.setFormatter(formatter)
        access_logger.addHandler(handler)
    access_logger.setLevel(log_level)

    if app is not None:
        app.logger = app_logger
