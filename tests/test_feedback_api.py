import types

import pytest
from app.routers import feedback_api


def _dummy_request(tenant_id: str = "tenant-123"):
    return types.SimpleNamespace(
        state=types.SimpleNamespace(tenant_id=tenant_id),
        headers={},
    )


def test_submit_feedback_sets_tenant(monkeypatch):
    executed: list[tuple[str, tuple]] = []

    class DummyCursor:
        def __init__(self, statements):
            self._statements = statements

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=None):
            self._statements.append((sql, params))

    class DummyConn:
        def __init__(self):
            self.statements = executed
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return DummyCursor(self.statements)

        def commit(self):
            self.committed = True

    dummy_conn = DummyConn()

    monkeypatch.setattr(feedback_api, "_DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(
        feedback_api, "psycopg", types.SimpleNamespace(connect=lambda url: dummy_conn)
    )
    monkeypatch.setattr(feedback_api, "ensure_schema", lambda conn: None)

    payload = feedback_api.FeedbackIn(
        helpful=True, question="q", answer=None, sessionId="s1", sources=None
    )

    result = feedback_api.submit_feedback(payload, _dummy_request())

    assert result.id
    assert dummy_conn.committed
    assert executed[0][0].strip().upper().startswith("SET APP.TENANT_ID")
    insert_stmt = next(sql for sql in executed if "INSERT INTO feedbacks" in sql[0])
    assert insert_stmt[1][1] == "tenant-123"


def test_submit_feedback_requires_tenant(monkeypatch):
    monkeypatch.setattr(feedback_api, "_DATABASE_URL", "postgresql://test")

    with pytest.raises(feedback_api.HTTPException) as exc:
        feedback_api.submit_feedback(
            feedback_api.FeedbackIn(helpful=True),
            types.SimpleNamespace(
                state=types.SimpleNamespace(tenant_id=None), headers={}
            ),
        )
    assert exc.value.status_code == 400
    assert "Tenant" in exc.value.detail
