import importlib
import importlib
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.agents import service as agent_service_module


def create_client(monkeypatch, tenant_auth):
    import app.routers.agents as agents_router
    importlib.reload(agents_router)

    provider_registry = agent_service_module.ProviderRegistry({"openai": {"api_key": "test"}})
    svc = agent_service_module.AgentService(
        agent_service_module.InMemoryAgentRepository(),
        provider_registry=provider_registry,
        prompt_store=agent_service_module.PromptTemplateStore(),
        response_store=agent_service_module.ResponseParameterStore({"openai": {"temperature": 0.6}}),
    )

    @contextmanager
    def fake_context():
        yield svc

    monkeypatch.setattr(agents_router, "_service_context", fake_context)

    import app.security.auth as auth
    importlib.reload(auth)
    import app.main as main
    importlib.reload(main)

    return TestClient(main.app), svc, tenant_auth


def test_agent_crud_and_deploy_flow(monkeypatch, tenant_auth):
    client, svc, auth_ctx = create_client(monkeypatch, tenant_auth)

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
    assert svc.list_agents() == []
