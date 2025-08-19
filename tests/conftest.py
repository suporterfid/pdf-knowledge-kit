import pathlib
import sys

import pytest
from fastapi import FastAPI, Request

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.app_logging import init_logging


@pytest.fixture
def app_factory(monkeypatch):
    def _create_app(log_dir: str, log_request_bodies: bool = False):
        """Create a FastAPI app with logging initialised."""
        monkeypatch.setenv("LOG_DIR", str(log_dir))
        if log_request_bodies:
            monkeypatch.setenv("LOG_REQUEST_BODIES", "true")
        app = FastAPI()

        @app.post("/echo")
        async def echo(request: Request):
            return await request.json()

        init_logging(app)
        return app

    return _create_app
