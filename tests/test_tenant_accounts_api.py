import importlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import RefreshToken, User


def create_client(monkeypatch, tenant_auth):
    import app.security.auth as security_auth
    importlib.reload(security_auth)
    import app.routers.tenant_accounts as tenant_router
    importlib.reload(tenant_router)
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app)


def test_register_login_refresh_logout(monkeypatch, tenant_auth):
    client = create_client(monkeypatch, tenant_auth)

    register_payload = {
        "organization_name": "New Org",
        "subdomain": f"org-{uuid4().hex[:6]}",
        "admin_name": "Org Owner",
        "admin_email": "owner@neworg.example",
        "password": "SuperSecret123!",
    }

    response = client.post("/api/tenant/accounts/register", json=register_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "owner@neworg.example"
    assert data["user"]["role"] == "admin"

    login_response = client.post(
        "/api/tenant/accounts/login",
        json={"email": register_payload["admin_email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    refresh_token = login_data["tokens"]["refresh_token"]

    refresh_response = client.post(
        "/api/tenant/accounts/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()["tokens"]
    new_refresh = refreshed["refresh_token"]
    access_token = refreshed["access_token"]

    reuse_response = client.post(
        "/api/tenant/accounts/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reuse_response.status_code == 401

    logout_response = client.post(
        "/api/tenant/accounts/logout",
        json={"refresh_token": new_refresh},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 204

    post_logout = client.post(
        "/api/tenant/accounts/refresh",
        json={"refresh_token": new_refresh},
    )
    assert post_logout.status_code == 401


def test_invite_accept_and_rotate(monkeypatch, tenant_auth):
    client = create_client(monkeypatch, tenant_auth)

    invite_payload = {
        "email": "analyst@tenant.example",
        "role": "viewer",
        "expires_in": 3600,
        "message": "Welcome!",
    }

    invite_response = client.post(
        "/api/tenant/accounts/invite",
        json=invite_payload,
        headers=tenant_auth.header("admin"),
    )
    assert invite_response.status_code == 201
    invite_token = invite_response.json()["token"]

    accept_response = client.post(
        "/api/tenant/accounts/accept-invite",
        json={"token": invite_token, "name": "Analyst", "password": tenant_auth.password},
    )
    assert accept_response.status_code == 200
    accepted = accept_response.json()
    new_refresh = accepted["tokens"]["refresh_token"]
    new_access = accepted["tokens"]["access_token"]

    with tenant_auth.session_factory() as session:
        user = session.execute(
            select(User).where(User.email == "analyst@tenant.example")
        ).scalar_one()
        assert user.role == "viewer"
        token_row = session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id)).scalar_one()
        assert token_row.revoked_at is None

    rotate_response = client.post(
        "/api/tenant/accounts/rotate-credentials",
        json={"refresh_token": new_refresh},
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert rotate_response.status_code == 200
    rotated = rotate_response.json()["tokens"]
    rotated_refresh = rotated["refresh_token"]

    reuse_old_refresh = client.post(
        "/api/tenant/accounts/refresh",
        json={"refresh_token": new_refresh},
    )
    assert reuse_old_refresh.status_code == 401

    refresh_rotated = client.post(
        "/api/tenant/accounts/refresh",
        json={"refresh_token": rotated_refresh},
    )
    assert refresh_rotated.status_code == 200
