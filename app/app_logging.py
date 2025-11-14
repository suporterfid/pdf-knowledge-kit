"""Application and access logging setup.

This module centralizes logging configuration for the FastAPI app. It provides:

- A simple JSON formatter (opt-in via LOG_JSON) or a human-readable formatter.
- Timed rotation of log files for both application logs (app.log) and access
  logs (access.log), honoring retention and timezone options.
- An HTTP middleware that records structured access logs (method, path,
  status, latency, client IP, headers, optional body) with basic PII scrubbing.

Environment variables (see README for details): LOG_DIR, LOG_LEVEL, LOG_JSON,
LOG_REQUEST_BODIES, LOG_RETENTION_DAYS, LOG_ROTATE_UTC.
"""

from __future__ import annotations

import json
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter used when LOG_JSON=true."""

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


SENSITIVE_FIELDS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "token",
    "access_token",
    "refresh_token",
}


def _scrub(data: object) -> object:
    """Recursively scrub sensitive fields from dictionaries and lists."""

    if isinstance(data, dict):
        return {
            k: ("***" if k.lower() in SENSITIVE_FIELDS else _scrub(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_scrub(v) for v in data]
    return data


def _install_access_logging(app: FastAPI) -> None:
    """Install request/response access logging middleware.

    The middleware logs one JSON line per request (excluding health/metrics),
    including a generated X-Request-Id that is also echoed back in the
    response headers for easy correlation.
    """

    log_request_bodies = os.getenv("LOG_REQUEST_BODIES", "false").lower() == "true"
    skip_paths = {"/api/health", "/api/metrics"}
    access_logger = logging.getLogger("uvicorn.access")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        if request.url.path in skip_paths:
            return await call_next(request)

        request_id = request.headers.get("X-Request-Id") or uuid4().hex
        request.state.request_id = request_id

        start = time.time()

        body_content = None
        if log_request_bodies:
            body_bytes = await request.body()

            async def receive() -> dict:  # pragma: no cover - internal
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]

            if body_bytes:
                try:
                    body_json = json.loads(body_bytes)
                    body_content = _scrub(body_json)
                except Exception:
                    body_content = body_bytes.decode("utf-8", errors="replace")

        response = await call_next(request)

        process_time_ms = (time.time() - start) * 1000
        client = request.client
        client_ip = request.headers.get("X-Forwarded-For")
        if not client_ip and client is not None:
            client_ip = client.host

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(process_time_ms, 2),
            "client_ip": client_ip,
            "headers": _scrub(dict(request.headers)),
        }

        if body_content is not None:
            log_data["body"] = body_content

        response.headers["X-Request-Id"] = request_id

        access_logger.info(json.dumps(log_data, default=str))
        return response


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
    access_logger.handlers.clear()
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
        cast(Any, app).logger = app_logger
        _install_access_logging(app)
