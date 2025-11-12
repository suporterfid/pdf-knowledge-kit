"""Regression tests for :mod:`app.agents.service`."""

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
