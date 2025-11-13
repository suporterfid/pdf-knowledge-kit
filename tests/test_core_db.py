"""Tests for tenant-aware database helpers."""

from uuid import uuid4

import pytest
from app.core.db import get_required_tenant_id
from app.core.tenant_context import reset_tenant_context, set_tenant_context


def test_get_required_tenant_id_from_context():
    tenant = uuid4()
    token = set_tenant_context(str(tenant), "user-123")
    try:
        assert get_required_tenant_id() == tenant
    finally:
        reset_tenant_context(token)


def test_get_required_tenant_id_invalid_raises():
    with pytest.raises(RuntimeError):
        get_required_tenant_id()

    with pytest.raises(RuntimeError):
        get_required_tenant_id("not-a-uuid")
