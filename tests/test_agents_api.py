import importlib
import sys
import types
from contextlib import contextmanager
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.agents import service as agent_service_module
from app.core import tenant_context


def create_client(monkeypatch, tenant_auth):
    if "email_validator" not in sys.modules:
        sys.modules["email_validator"] = types.SimpleNamespace(
            validate_email=lambda value, **kwargs: types.SimpleNamespace(email=value),
            caching_resolver=None,
            EmailNotValidError=ValueError,
        )

    import pydantic.networks as pydantic_networks

    monkeypatch.setattr(pydantic_networks, "import_email_validator", lambda: None)

    import app.routers.agents as agents_router
    importlib.reload(agents_router)

    provider_registry = agent_service_module.ProviderRegistry({"openai": {"api_key": "test"}})
    prompt_store = agent_service_module.PromptTemplateStore()
    response_store = agent_service_module.ResponseParameterStore({"openai": {"temperature": 0.6}})
    class StrictInMemoryRepository(agent_service_module.InMemoryAgentRepository):
        def delete_agent(self, agent_id: int) -> None:  # type: ignore[override]
            if agent_id not in self._agents:
                raise agent_service_module.AgentNotFoundError(f"Agent {agent_id} not found")
            super().delete_agent(agent_id)

    tenant_services: dict[str, agent_service_module.AgentService] = {}

    @contextmanager
    def fake_context():
        current_tenant = tenant_context.get_current_tenant_id()
        if current_tenant is None:  # pragma: no cover - enforced by middleware in tests
            raise RuntimeError("tenant context missing")
        tenant_key = str(current_tenant)
        svc = tenant_services.get(tenant_key)
        if svc is None:
            repository = StrictInMemoryRepository(
                tenant_id=UUID(tenant_key)
            )
            svc = agent_service_module.AgentService(
                repository,
                tenant_id=UUID(tenant_key),
                provider_registry=provider_registry,
                prompt_store=prompt_store,
                response_store=response_store,
            )
            tenant_services[tenant_key] = svc
        try:
            yield svc
        except agent_service_module.AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    monkeypatch.setattr(agents_router, "_service_context", fake_context)

    import app.security.auth as auth
    importlib.reload(auth)
    import app.main as main
    importlib.reload(main)

    return TestClient(main.app), tenant_services, tenant_auth


def test_agent_crud_and_deploy_flow(monkeypatch, tenant_auth):
    client, services, auth_ctx = create_client(monkeypatch, tenant_auth)

    create_payload = {
        "name": "Support Bot",
        "description": "Helps customers with product questions",
        "provider": "openai",
        "model": "gpt-4o",
        "persona": {"tone": "warm", "style": "detailed"},
        "persona_type": "support",
        "response_parameters": {"temperature": 0.4},
        "initial_version_label": "v1",
        "tags": ["support"],
    }

    res = client.post("/api/agents", json=create_payload, headers=auth_ctx.header("operator"))
    assert res.status_code == 201
    agent_detail = res.json()
    agent_id = agent_detail["id"]
    assert agent_detail["deployment_metadata"]["provider_credentials"]["configured"]

    res = client.get("/api/agents", headers=auth_ctx.header("viewer"))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Support Bot"

    res = client.get("/api/agents/providers", headers=auth_ctx.header("viewer"))
    assert res.status_code == 200
    providers = res.json()
    assert "openai" in providers

    update_payload = {
        "description": "Updated description",
        "response_parameters": {"temperature": 0.2},
        "prompt_template": "You are a careful support representative.",
    }
    res = client.put(
        f"/api/agents/{agent_id}",
        json=update_payload,
        headers=auth_ctx.header("operator"),
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["description"] == "Updated description"
    assert updated["response_parameters"]["temperature"] == 0.2

    res = client.get(f"/api/agents/{agent_id}/versions", headers=auth_ctx.header("viewer"))
    assert res.status_code == 200
    versions = res.json()
    assert versions["total"] == 1

    res = client.post(
        f"/api/agents/{agent_id}/test",
        json={"input": "How do I reset my password?"},
        headers=auth_ctx.header("operator"),
    )
    assert res.status_code == 200
    test_result = res.json()
    assert "Agent Support Bot" in test_result["output"]

    res = client.post(
        f"/api/agents/{agent_id}/deploy",
        json={"environment": "staging", "metadata": {"requested_by": "qa"}},
        headers=auth_ctx.header("operator"),
    )
    assert res.status_code == 200
    deployed = res.json()
    assert deployed["deployment_metadata"]["environments"]["staging"]["metadata"]["requested_by"] == "qa"

    res = client.get(f"/api/agents/{agent_id}/tests", headers=auth_ctx.header("viewer"))
    assert res.status_code == 200
    tests = res.json()
    assert len(tests) == 1

    res = client.delete(f"/api/agents/{agent_id}", headers=auth_ctx.header("operator"))
    assert res.status_code == 200
    assert res.json()["message"] == "deleted"

    res = client.get("/api/agents", headers=auth_ctx.header("viewer"))
    assert res.json()["total"] == 0

    # ensure underlying service reflects deletion
    tenant_id = str(auth_ctx.organization_id)
    assert services[tenant_id].list_agents() == []


def test_agents_cross_tenant_isolation(monkeypatch, tenant_auth):
    client, services, auth_ctx = create_client(monkeypatch, tenant_auth)

    create_payload = {
        "name": "Primary Agent",
        "description": "Belongs to primary tenant",
        "provider": "openai",
        "model": "gpt-4o",
        "persona": {"tone": "warm"},
        "persona_type": "support",
        "response_parameters": {"temperature": 0.2},
        "initial_version_label": "v1",
    }

    res = client.post("/api/agents", json=create_payload, headers=auth_ctx.header("operator"))
    assert res.status_code == 201
    agent_id = res.json()["id"]

    other_tenant = auth_ctx.create_tenant("Other", "other")

    res = client.get("/api/agents", headers=auth_ctx.header("viewer", tenant_id=other_tenant))
    assert res.status_code == 200
    assert res.json()["total"] == 0

    res = client.get(
        f"/api/agents/{agent_id}",
        headers=auth_ctx.header("viewer", tenant_id=other_tenant),
    )
    assert res.status_code == 404

    res = client.post(
        f"/api/agents/{agent_id}/test",
        json={"input": "hello"},
        headers=auth_ctx.header("operator", tenant_id=other_tenant),
    )
    assert res.status_code == 404

    res = client.delete(
        f"/api/agents/{agent_id}",
        headers=auth_ctx.header("operator", tenant_id=other_tenant),
    )
    assert res.status_code == 404

    primary_key = str(auth_ctx.organization_id)
    assert services[primary_key].list_agents()
    assert services[str(other_tenant)].list_agents() == []
