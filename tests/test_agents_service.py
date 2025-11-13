"""Regression tests for :mod:`app.agents.service`."""

from uuid import uuid4

from app.agents import schemas
from app.agents.service import AgentService, InMemoryAgentRepository


def test_get_agent_by_slug_with_inmemory_repository():
    repository = InMemoryAgentRepository()
    service = AgentService(repository)

    payload = schemas.AgentCreate(
        name="Support Bot",
        description="Helps customers with common issues",
        provider="openai",
        model="gpt-4o-mini",
        persona={"type": "support"},
        response_parameters={"temperature": 0.2},
    )

    created = service.create_agent(payload)

    fetched = service.get_agent_by_slug(created.slug)

    assert fetched.id == created.id
    assert fetched.slug == created.slug
    assert fetched.name == payload.name
    assert fetched.versions, "Expected versions to be included by default"
    assert fetched.latest_version is not None
    assert fetched.tests == []


def test_run_test_records_tenant_id():
    tenant_id = uuid4()
    repository = InMemoryAgentRepository(tenant_id=tenant_id)
    service = AgentService(repository, tenant_id=tenant_id)

    agent = service.create_agent(
        schemas.AgentCreate(
            name="Support Bot",
            description="Helps customers",
            provider="openai",
            model="gpt-4o-mini",
            persona={"type": "support"},
            response_parameters={"temperature": 0.1},
        )
    )

    service.run_test(agent.id, schemas.AgentTestRequest(input="Hello"))

    records = service.list_tests(agent.id)
    assert records, "Expected a test record to be created"
    assert records[0].tenant_id == tenant_id
