"""Pydantic schemas for agent management APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base configuration shared by create/update operations."""

    name: str
    description: Optional[str] = None
    provider: str
    model: str
    persona: Dict[str, Any] = Field(default_factory=dict)
    prompt_template: Optional[str] = None
    response_parameters: Dict[str, Any] = Field(default_factory=dict)
    deployment_metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_by: Optional[str] = None
    persona_type: Optional[str] = None


class AgentCreate(AgentBase):
    """Payload used to create a new agent."""

    initial_version_label: Optional[str] = None


class AgentUpdate(BaseModel):
    """Patchable agent fields."""

    name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    prompt_template: Optional[str] = None
    response_parameters: Optional[Dict[str, Any]] = None
    deployment_metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    persona_type: Optional[str] = None
    created_by: Optional[str] = None


class AgentVersionConfig(BaseModel):
    provider: str
    model: str
    persona: Dict[str, Any] = Field(default_factory=dict)
    prompt_template: Optional[str] = None
    response_parameters: Dict[str, Any] = Field(default_factory=dict)


class AgentVersion(BaseModel):
    id: int
    agent_id: int
    version: int
    label: Optional[str] = None
    created_by: Optional[str] = None
    config: AgentVersionConfig
    prompt_template: Optional[str] = None
    persona: Dict[str, Any] = Field(default_factory=dict)
    response_parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Agent(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    provider: str
    model: str
    persona: Dict[str, Any] = Field(default_factory=dict)
    prompt_template: Optional[str] = None
    response_parameters: Dict[str, Any] = Field(default_factory=dict)
    deployment_metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[AgentVersion] = None


class AgentDetail(Agent):
    versions: List[AgentVersion] = Field(default_factory=list)
    tests: List["AgentTestRecord"] = Field(default_factory=list)


class AgentVersionCreate(BaseModel):
    label: Optional[str] = None
    created_by: Optional[str] = None
    config: AgentVersionConfig


class AgentVersionList(BaseModel):
    items: List[AgentVersion]
    total: int


class AgentList(BaseModel):
    items: List[Agent]
    total: int


class AgentTestRequest(BaseModel):
    input: str = Field(..., description="Prompt to send to the agent")
    channel: Optional[str] = None
    response_overrides: Dict[str, Any] = Field(default_factory=dict)


class AgentTestRecord(BaseModel):
    id: int
    agent_id: int
    agent_version_id: Optional[int] = None
    input_prompt: str
    response: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    status: str
    channel: Optional[str] = None
    ran_at: datetime


class AgentTestRecordCreate(BaseModel):
    agent_id: int
    agent_version_id: Optional[int] = None
    input_prompt: str
    response: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    status: str = "success"
    channel: Optional[str] = None


class AgentTestResponse(BaseModel):
    status: str
    output: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rendered_prompt: str
    record: AgentTestRecord


class AgentDeployRequest(BaseModel):
    environment: str
    endpoint_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentDeployResponse(AgentDetail):
    pass




class ChannelConfig(BaseModel):
    channel: str
    is_enabled: bool = True
    webhook_secret: Optional[str] = None
    credentials: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChannelConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    webhook_secret: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class ChannelConfigList(BaseModel):
    items: List[ChannelConfig]
    total: int


class Message(BaseModel):
    message: str

try:  # Pydantic v2
    AgentDetail.model_rebuild()
    AgentTestResponse.model_rebuild()
except AttributeError:  # pragma: no cover - Pydantic v1 fallback
    AgentDetail.update_forward_refs()
    AgentTestResponse.update_forward_refs()
