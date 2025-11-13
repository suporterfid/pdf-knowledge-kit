"""Pydantic schemas for agent management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base configuration shared by create/update operations."""

    tenant_id: UUID | None = None
    name: str
    description: str | None = None
    provider: str
    model: str
    persona: dict[str, Any] = Field(default_factory=dict)
    prompt_template: str | None = None
    response_parameters: dict[str, Any] = Field(default_factory=dict)
    deployment_metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_by: str | None = None
    persona_type: str | None = None


class AgentCreate(AgentBase):
    """Payload used to create a new agent."""

    initial_version_label: str | None = None


class AgentUpdate(BaseModel):
    """Patchable agent fields."""

    name: str | None = None
    description: str | None = None
    provider: str | None = None
    model: str | None = None
    persona: dict[str, Any] | None = None
    prompt_template: str | None = None
    response_parameters: dict[str, Any] | None = None
    deployment_metadata: dict[str, Any] | None = None
    tags: list[str] | None = None
    is_active: bool | None = None
    persona_type: str | None = None
    created_by: str | None = None


class AgentVersionConfig(BaseModel):
    provider: str
    model: str
    persona: dict[str, Any] = Field(default_factory=dict)
    prompt_template: str | None = None
    response_parameters: dict[str, Any] = Field(default_factory=dict)


class AgentVersion(BaseModel):
    id: int
    tenant_id: UUID
    agent_id: int
    version: int
    label: str | None = None
    created_by: str | None = None
    config: AgentVersionConfig
    prompt_template: str | None = None
    persona: dict[str, Any] = Field(default_factory=dict)
    response_parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Agent(BaseModel):
    id: int
    tenant_id: UUID
    slug: str
    name: str
    description: str | None = None
    provider: str
    model: str
    persona: dict[str, Any] = Field(default_factory=dict)
    prompt_template: str | None = None
    response_parameters: dict[str, Any] = Field(default_factory=dict)
    deployment_metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime
    latest_version: AgentVersion | None = None


class AgentDetail(Agent):
    versions: list[AgentVersion] = Field(default_factory=list)
    tests: list[AgentTestRecord] = Field(default_factory=list)


class AgentVersionCreate(BaseModel):
    label: str | None = None
    created_by: str | None = None
    config: AgentVersionConfig


class AgentVersionList(BaseModel):
    items: list[AgentVersion]
    total: int


class AgentList(BaseModel):
    items: list[Agent]
    total: int


class AgentTestRequest(BaseModel):
    input: str = Field(..., description="Prompt to send to the agent")
    channel: str | None = None
    response_overrides: dict[str, Any] = Field(default_factory=dict)


class AgentTestRecord(BaseModel):
    id: int
    tenant_id: UUID
    agent_id: int
    agent_version_id: int | None = None
    input_prompt: str
    response: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    status: str
    channel: str | None = None
    ran_at: datetime


class AgentTestRecordCreate(BaseModel):
    tenant_id: UUID | None = None
    agent_id: int
    agent_version_id: int | None = None
    input_prompt: str
    response: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    status: str = "success"
    channel: str | None = None


class AgentTestResponse(BaseModel):
    status: str
    output: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    rendered_prompt: str
    record: AgentTestRecord


class AgentDeployRequest(BaseModel):
    environment: str
    endpoint_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentDeployResponse(AgentDetail):
    pass


class ChannelConfig(BaseModel):
    tenant_id: UUID
    channel: str
    is_enabled: bool = True
    webhook_secret: str | None = None
    credentials: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChannelConfigUpdate(BaseModel):
    is_enabled: bool | None = None
    webhook_secret: str | None = None
    credentials: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


class ChannelConfigList(BaseModel):
    items: list[ChannelConfig]
    total: int


class Message(BaseModel):
    message: str


try:  # Pydantic v2
    AgentDetail.model_rebuild()
    AgentTestResponse.model_rebuild()
except AttributeError:  # pragma: no cover - Pydantic v1 fallback
    AgentDetail.update_forward_refs()
    AgentTestResponse.update_forward_refs()
