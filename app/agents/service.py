"""Service layer orchestrating agent CRUD, testing and deployment."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Dict, Iterable, Iterator, List, Optional, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import schemas
from .providers import ProviderRegistry
from .prompts import PromptTemplateStore
from .responses import ResponseParameterStore


class AgentNotFoundError(RuntimeError):
    """Raised when an agent could not be located."""


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"


class AgentRepository(Protocol):
    """Persistence abstraction used by :class:`AgentService`."""

    def list_agents(self) -> List[schemas.Agent]: ...

    def get_agent(
        self, agent_id: int, *, include_versions: bool = False, include_tests: bool = False
    ) -> Optional[schemas.AgentDetail]: ...

    def get_agent_by_slug(
        self, slug: str, *, include_versions: bool = False, include_tests: bool = False
    ) -> Optional[schemas.AgentDetail]: ...

    def create_agent(self, payload: schemas.AgentCreate) -> schemas.Agent: ...

    def update_agent(self, agent_id: int, payload: schemas.AgentUpdate) -> schemas.Agent: ...

    def delete_agent(self, agent_id: int) -> None: ...

    def create_version(self, agent_id: int, payload: schemas.AgentVersionCreate) -> schemas.AgentVersion: ...

    def list_versions(self, agent_id: int) -> List[schemas.AgentVersion]: ...

    def latest_version(self, agent_id: int) -> Optional[schemas.AgentVersion]: ...

    def record_test(self, payload: schemas.AgentTestRecordCreate) -> schemas.AgentTestRecord: ...

    def list_tests(self, agent_id: int, limit: int = 20) -> List[schemas.AgentTestRecord]: ...

    def update_deployment_metadata(self, agent_id: int, metadata: Dict[str, Any]) -> schemas.Agent: ...

    def list_channel_configs(self, agent_id: int) -> List[schemas.ChannelConfig]: ...

    def get_channel_config(self, agent_id: int, channel: str) -> Optional[schemas.ChannelConfig]: ...

    def upsert_channel_config(
        self, agent_id: int, channel: str, payload: schemas.ChannelConfigUpdate
    ) -> schemas.ChannelConfig: ...

    def delete_channel_config(self, agent_id: int, channel: str) -> None: ...


class AgentService:
    """High-level orchestration for managing agents."""

    def __init__(
        self,
        repository: AgentRepository,
        provider_registry: Optional[ProviderRegistry] = None,
        prompt_store: Optional[PromptTemplateStore] = None,
        response_store: Optional[ResponseParameterStore] = None,
    ) -> None:
        self._repository = repository
        self._providers = provider_registry or ProviderRegistry()
        self._prompts = prompt_store or PromptTemplateStore()
        self._responses = response_store or ResponseParameterStore()

    # ------------------------------------------------------------------
    # CRUD operations

    def list_agents(self) -> List[schemas.Agent]:
        return self._repository.list_agents()

    def get_agent(
        self,
        agent_id: int,
        *,
        include_versions: bool = True,
        include_tests: bool = True,
    ) -> schemas.AgentDetail:
        agent = self._repository.get_agent(
            agent_id,
            include_versions=include_versions,
            include_tests=include_tests,
        )
        if not agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        return agent

    def get_agent_by_slug(
        self,
        slug: str,
        *,
        include_versions: bool = True,
        include_tests: bool = False,
    ) -> schemas.AgentDetail:
        agent = self._repository.get_agent_by_slug(
            slug,
            include_versions=include_versions,
            include_tests=include_tests,
        )
        if not agent:
            raise AgentNotFoundError(f"Agent '{slug}' not found")
        return agent

    def create_agent(self, payload: schemas.AgentCreate) -> schemas.AgentDetail:
        persona = dict(payload.persona or {})
        if payload.persona_type:
            persona.setdefault("type", payload.persona_type)
        persona.setdefault("type", persona.get("type", "general"))
        prompt_template = self._prompts.resolve(persona, payload.provider, payload.prompt_template)
        response_parameters = self._responses.merge(payload.provider, payload.response_parameters)
        credentials = self._providers.get_credentials(payload.provider)
        cleaned_payload = _normalise_create_payload(
            payload,
            persona,
            prompt_template,
            response_parameters,
            bool(credentials.api_key),
        )
        agent = self._repository.create_agent(cleaned_payload)
        version_config = schemas.AgentVersionConfig(
            provider=agent.provider,
            model=agent.model,
            persona=agent.persona,
            prompt_template=agent.prompt_template,
            response_parameters=agent.response_parameters,
        )
        version_payload = schemas.AgentVersionCreate(
            label=payload.initial_version_label or "v1",
            created_by=payload.created_by,
            config=version_config,
        )
        version = self._repository.create_version(agent.id, version_payload)
        agent.latest_version = version
        return self.get_agent(agent.id)

    def update_agent(self, agent_id: int, payload: schemas.AgentUpdate) -> schemas.AgentDetail:
        existing = self._repository.get_agent(agent_id)
        if not existing:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        persona = dict(payload.persona or existing.persona)
        if payload.persona_type:
            persona.setdefault("type", payload.persona_type)
        prompt_template = self._prompts.resolve(
            persona,
            payload.provider or existing.provider,
            payload.prompt_template or existing.prompt_template,
        )
        response_parameters = self._responses.merge(
            payload.provider or existing.provider,
            existing.response_parameters,
            payload.response_parameters,
        )
        credentials = self._providers.get_credentials(payload.provider or existing.provider)
        merged_payload = _normalise_update_payload(
            payload,
            persona,
            prompt_template,
            response_parameters,
            bool(credentials.api_key),
            existing.deployment_metadata,
        )
        self._repository.update_agent(agent_id, merged_payload)
        return self.get_agent(agent_id)

    def delete_agent(self, agent_id: int) -> None:
        self._repository.delete_agent(agent_id)

    # ------------------------------------------------------------------
    # Versions

    def create_version(self, agent_id: int, payload: schemas.AgentVersionCreate) -> schemas.AgentVersion:
        existing = self._repository.get_agent(agent_id)
        if not existing:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        version = self._repository.create_version(agent_id, payload)
        return version

    def list_versions(self, agent_id: int) -> List[schemas.AgentVersion]:
        return self._repository.list_versions(agent_id)

    # ------------------------------------------------------------------
    # Testing & deployment

    def run_test(self, agent_id: int, request: schemas.AgentTestRequest) -> schemas.AgentTestResponse:
        agent = self._repository.get_agent(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        latest_version = agent.latest_version or self._repository.latest_version(agent_id)
        parameters = self._responses.merge(agent.provider, agent.response_parameters, request.response_overrides)
        prompt_template = agent.prompt_template or self._prompts.resolve(agent.persona, agent.provider, None)
        rendered_prompt = self._prompts.render(prompt_template, agent.persona, request.input)
        credentials = self._providers.get_credentials(agent.provider)
        # Sandboxed execution: we don't call real LLMs in tests, instead echo behaviour.
        output = _simulate_model_response(agent.name, rendered_prompt, parameters)
        record_payload = schemas.AgentTestRecordCreate(
            agent_id=agent.id,
            agent_version_id=latest_version.id if latest_version else None,
            input_prompt=request.input,
            response={"text": output},
            metrics={
                "provider": agent.provider,
                "temperature": parameters.get("temperature"),
                "credential_present": bool(credentials.api_key),
            },
            status="success",
            channel=request.channel,
        )
        record = self._repository.record_test(record_payload)
        return schemas.AgentTestResponse(
            status="success",
            output=output,
            parameters=parameters,
            rendered_prompt=rendered_prompt,
            record=record,
        )

    def deploy_agent(self, agent_id: int, request: schemas.AgentDeployRequest) -> schemas.AgentDetail:
        agent = self._repository.get_agent(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        metadata = dict(agent.deployment_metadata)
        environments = metadata.setdefault("environments", {})
        environments[request.environment] = {
            "endpoint_url": request.endpoint_url,
            "metadata": request.metadata,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }
        updated_agent = self._repository.update_deployment_metadata(agent_id, metadata)
        return self.get_agent(updated_agent.id)

    def list_tests(self, agent_id: int, limit: int = 20) -> List[schemas.AgentTestRecord]:
        return self._repository.list_tests(agent_id, limit=limit)

    def list_supported_providers(self) -> Dict[str, Optional[str]]:
        return self._providers.list_supported_providers()

    # ------------------------------------------------------------------
    # Channels

    def list_channel_configs(self, agent_id: int) -> List[schemas.ChannelConfig]:
        return self._repository.list_channel_configs(agent_id)

    def get_channel_config(self, agent_id: int, channel: str) -> schemas.ChannelConfig:
        config = self._repository.get_channel_config(agent_id, channel.lower())
        if not config:
            raise AgentNotFoundError(f"Channel {channel} not configured for agent {agent_id}")
        return config

    def upsert_channel_config(
        self, agent_id: int, channel: str, payload: schemas.ChannelConfigUpdate
    ) -> schemas.ChannelConfig:
        return self._repository.upsert_channel_config(agent_id, channel.lower(), payload)

    def delete_channel_config(self, agent_id: int, channel: str) -> None:
        self._repository.delete_channel_config(agent_id, channel.lower())



def _simulate_model_response(name: str, rendered_prompt: str, parameters: Dict[str, Any]) -> str:
    preview = rendered_prompt.splitlines()[-1] if rendered_prompt else ""
    return f"Agent {name} (temp={parameters.get('temperature')}) would reply to: {preview}"


def _normalise_create_payload(
    payload: schemas.AgentCreate,
    persona: Dict[str, Any],
    prompt_template: str,
    response_parameters: Dict[str, Any],
    credentials_available: bool,
) -> schemas.AgentCreate:
    data = _model_dump(payload, exclude={"initial_version_label"})
    data.update(
        {
            "persona": persona,
            "prompt_template": prompt_template,
            "response_parameters": response_parameters,
            "deployment_metadata": data.get("deployment_metadata") or {},
            "tags": data.get("tags") or [],
        }
    )
    metadata = dict(data["deployment_metadata"])
    metadata.setdefault("provider_credentials", {})
    metadata["provider_credentials"]["configured"] = credentials_available
    data["deployment_metadata"] = metadata
    return schemas.AgentCreate(**data)


def _normalise_update_payload(
    payload: schemas.AgentUpdate,
    persona: Dict[str, Any],
    prompt_template: str,
    response_parameters: Dict[str, Any],
    credentials_available: Optional[bool],
    existing_metadata: Optional[Dict[str, Any]],
) -> schemas.AgentUpdate:
    data = _model_dump(payload)
    if payload.persona is not None or payload.persona_type is not None:
        data["persona"] = persona
    data["prompt_template"] = prompt_template
    data["response_parameters"] = response_parameters
    metadata = dict(existing_metadata or {})
    if "deployment_metadata" in data:
        incoming = data["deployment_metadata"] or {}
        metadata.update(incoming)
        data["deployment_metadata"] = metadata
    elif credentials_available is not None:
        metadata.setdefault("provider_credentials", {})
        metadata["provider_credentials"]["configured"] = credentials_available
        data["deployment_metadata"] = metadata
    if "deployment_metadata" not in data:
        data["deployment_metadata"] = metadata
    if "tags" in data and data["tags"] is None:
        data["tags"] = []
    return schemas.AgentUpdate(**data)


def _model_dump(model: Any, exclude: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    exclude = set(exclude or [])
    if hasattr(model, "model_dump"):
        return {
            k: v
            for k, v in model.model_dump().items()
            if k not in exclude and v is not None
        }
    return {k: v for k, v in model.dict().items() if k not in exclude and v is not None}


# ---------------------------------------------------------------------------
# Postgres repository implementation


@dataclass
class _ConnectionWrapper:
    conn: psycopg.Connection

    def cursor(self):
        return self.conn.cursor(row_factory=dict_row)


class PostgresAgentRepository:
    """PostgreSQL-backed agent repository."""

    def __init__(self, connection: psycopg.Connection):
        self._conn = connection

    def cursor(self):
        return self._conn.cursor(row_factory=dict_row)

    def list_agents(self) -> List[schemas.Agent]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, name, description, provider, model, persona, prompt_template,
                       response_params, deployment_metadata, tags, is_active, created_at, updated_at
                FROM agents
                ORDER BY name
                """
            )
            rows = cur.fetchall()
        agents = [self._row_to_agent(row) for row in rows]
        for agent in agents:
            agent.latest_version = self.latest_version(agent.id)
        return agents

    def get_agent(
        self, agent_id: int, *, include_versions: bool = False, include_tests: bool = False
    ) -> Optional[schemas.AgentDetail]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, name, description, provider, model, persona, prompt_template,
                       response_params, deployment_metadata, tags, is_active, created_at, updated_at
                FROM agents
                WHERE id = %s
                """,
                (agent_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        agent = self._row_to_agent(row)
        detail = schemas.AgentDetail(**agent.model_dump())
        if include_versions:
            detail.versions = self.list_versions(agent_id)
            detail.latest_version = detail.versions[-1] if detail.versions else None
        else:
            detail.latest_version = self.latest_version(agent_id)
        if include_tests:
            detail.tests = self.list_tests(agent_id)
        return detail

    def get_agent_by_slug(
        self, slug: str, *, include_versions: bool = False, include_tests: bool = False
    ) -> Optional[schemas.AgentDetail]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, name, description, provider, model, persona, prompt_template,
                       response_params, deployment_metadata, tags, is_active, created_at, updated_at
                FROM agents
                WHERE slug = %s
                """,
                (slug,),
            )
            row = cur.fetchone()
        if not row:
            return None
        agent = self._row_to_agent(row)
        detail = schemas.AgentDetail(**agent.model_dump())
        if include_versions:
            detail.versions = self.list_versions(agent.id)
            detail.latest_version = detail.versions[-1] if detail.versions else None
        else:
            detail.latest_version = self.latest_version(agent.id)
        if include_tests:
            detail.tests = self.list_tests(agent.id)
        return detail

    def create_agent(self, payload: schemas.AgentCreate) -> schemas.Agent:
        with self.cursor() as cur:
            slug = self._generate_unique_slug(cur, payload.name)
            cur.execute(
                """
                INSERT INTO agents
                    (slug, name, description, provider, model, persona, prompt_template,
                     response_params, deployment_metadata, tags, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, slug, name, description, provider, model, persona, prompt_template,
                          response_params, deployment_metadata, tags, is_active, created_at, updated_at
                """,
                (
                    slug,
                    payload.name,
                    payload.description,
                    payload.provider,
                    payload.model,
                    Jsonb(payload.persona),
                    payload.prompt_template,
                    Jsonb(payload.response_parameters),
                    Jsonb(payload.deployment_metadata or {}),
                    payload.tags,
                    payload.is_active,
                ),
            )
            row = cur.fetchone()
        agent = self._row_to_agent(row)
        return agent

    def _generate_unique_slug(self, cur, name: str) -> str:
        base = _slugify(name)
        candidate = base
        suffix = 1
        while True:
            cur.execute("SELECT 1 FROM agents WHERE slug = %s", (candidate,))
            if cur.fetchone() is None:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def update_agent(self, agent_id: int, payload: schemas.AgentUpdate) -> schemas.Agent:
        fields: List[str] = []
        values: List[Any] = []
        data = _model_dump(payload)
        for key, value in data.items():
            if key == "persona":
                fields.append("persona = %s")
                values.append(Jsonb(value))
            elif key == "response_parameters":
                fields.append("response_params = %s")
                values.append(Jsonb(value))
            elif key == "deployment_metadata":
                fields.append("deployment_metadata = %s")
                values.append(Jsonb(value))
            elif key == "prompt_template":
                fields.append("prompt_template = %s")
                values.append(value)
            elif key == "tags":
                fields.append("tags = %s")
                values.append(value)
            elif key == "persona_type":
                continue
            else:
                fields.append(f"{key} = %s")
                values.append(value)
        if not fields:
            agent = self.get_agent(agent_id)
            if not agent:
                raise AgentNotFoundError
            return agent
        set_clause = ", ".join(fields)
        query = f"UPDATE agents SET {set_clause} WHERE id = %s RETURNING id, slug, name, description, provider, model, persona, prompt_template, response_params, deployment_metadata, tags, is_active, created_at, updated_at"
        values.append(agent_id)
        with self.cursor() as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        if not row:
            raise AgentNotFoundError
        return self._row_to_agent(row)

    def delete_agent(self, agent_id: int) -> None:
        with self.cursor() as cur:
            cur.execute("DELETE FROM agents WHERE id = %s", (agent_id,))

    def create_version(self, agent_id: int, payload: schemas.AgentVersionCreate) -> schemas.AgentVersion:
        latest = self.latest_version(agent_id)
        next_version = (latest.version + 1) if latest else 1
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_versions
                    (agent_id, version, label, created_by, config, prompt_template, persona, response_params)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, agent_id, version, label, created_by, config, prompt_template, persona, response_params, created_at
                """,
                (
                    agent_id,
                    next_version,
                    payload.label,
                    payload.created_by,
                    Jsonb(payload.config.model_dump()),
                    payload.config.prompt_template,
                    Jsonb(payload.config.persona),
                    Jsonb(payload.config.response_parameters),
                ),
            )
            row = cur.fetchone()
        version = self._row_to_version(row)
        return version

    def list_versions(self, agent_id: int) -> List[schemas.AgentVersion]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_id, version, label, created_by, config, prompt_template, persona, response_params, created_at
                FROM agent_versions
                WHERE agent_id = %s
                ORDER BY version
                """,
                (agent_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_version(row) for row in rows]

    def latest_version(self, agent_id: int) -> Optional[schemas.AgentVersion]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_id, version, label, created_by, config, prompt_template, persona, response_params, created_at
                FROM agent_versions
                WHERE agent_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (agent_id,),
            )
            row = cur.fetchone()
        return self._row_to_version(row) if row else None

    def record_test(self, payload: schemas.AgentTestRecordCreate) -> schemas.AgentTestRecord:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_tests
                    (agent_version_id, agent_id, input_prompt, response, metrics, status, channel)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, agent_version_id, agent_id, input_prompt, response, metrics, status, channel, ran_at
                """,
                (
                    payload.agent_version_id,
                    payload.agent_id,
                    payload.input_prompt,
                    Jsonb(payload.response),
                    Jsonb(payload.metrics),
                    payload.status,
                    payload.channel,
                ),
            )
            row = cur.fetchone()
        return self._row_to_test(row)

    def list_tests(self, agent_id: int, limit: int = 20) -> List[schemas.AgentTestRecord]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_version_id, agent_id, input_prompt, response, metrics, status, channel, ran_at
                FROM agent_tests
                WHERE agent_id = %s
                ORDER BY ran_at DESC
                LIMIT %s
                """,
                (agent_id, limit),
            )
            rows = cur.fetchall()
        return [self._row_to_test(row) for row in rows]

    def update_deployment_metadata(self, agent_id: int, metadata: Dict[str, Any]) -> schemas.Agent:
        with self.cursor() as cur:
            cur.execute(
                """
                UPDATE agents
                SET deployment_metadata = %s
                WHERE id = %s
                RETURNING id, slug, name, description, provider, model, persona, prompt_template,
                          response_params, deployment_metadata, tags, is_active, created_at, updated_at
                """,
                (Jsonb(metadata), agent_id),
            )
            row = cur.fetchone()
        if not row:
            raise AgentNotFoundError
        return self._row_to_agent(row)

    # ------------------------------------------------------------------
    # Row converters
    def list_channel_configs(self, agent_id: int) -> List[schemas.ChannelConfig]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT channel, is_enabled, webhook_secret, credentials, settings, created_at, updated_at
                FROM agent_channel_configs
                WHERE agent_id = %s
                ORDER BY channel
                """,
                (agent_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_channel_config(row) for row in rows]

    def get_channel_config(self, agent_id: int, channel: str) -> Optional[schemas.ChannelConfig]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT channel, is_enabled, webhook_secret, credentials, settings, created_at, updated_at
                FROM agent_channel_configs
                WHERE agent_id = %s AND channel = %s
                """,
                (agent_id, channel),
            )
            row = cur.fetchone()
        return self._row_to_channel_config(row) if row else None

    def upsert_channel_config(
        self, agent_id: int, channel: str, payload: schemas.ChannelConfigUpdate
    ) -> schemas.ChannelConfig:
        existing = self.get_channel_config(agent_id, channel)
        is_enabled = payload.is_enabled if payload.is_enabled is not None else (existing.is_enabled if existing else True)
        webhook_secret = payload.webhook_secret if payload.webhook_secret is not None else (existing.webhook_secret if existing else None)
        credentials = payload.credentials if payload.credentials is not None else (existing.credentials if existing else {})
        settings = payload.settings if payload.settings is not None else (existing.settings if existing else {})
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_channel_configs (agent_id, channel, is_enabled, webhook_secret, credentials, settings)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (agent_id, channel) DO UPDATE
                SET is_enabled = EXCLUDED.is_enabled,
                    webhook_secret = EXCLUDED.webhook_secret,
                    credentials = EXCLUDED.credentials,
                    settings = EXCLUDED.settings,
                    updated_at = now()
                RETURNING channel, is_enabled, webhook_secret, credentials, settings, created_at, updated_at
                """,
                (
                    agent_id,
                    channel,
                    is_enabled,
                    webhook_secret,
                    Jsonb(credentials),
                    Jsonb(settings),
                ),
            )
            row = cur.fetchone()
        return self._row_to_channel_config(row)

    def delete_channel_config(self, agent_id: int, channel: str) -> None:
        with self.cursor() as cur:
            cur.execute("DELETE FROM agent_channel_configs WHERE agent_id = %s AND channel = %s", (agent_id, channel))


    def _row_to_agent(self, row: Dict[str, Any]) -> schemas.Agent:
        return schemas.Agent(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            description=row.get("description"),
            provider=row["provider"],
            model=row["model"],
            persona=row.get("persona") or {},
            prompt_template=row.get("prompt_template"),
            response_parameters=row.get("response_params") or {},
            deployment_metadata=row.get("deployment_metadata") or {},
            tags=list(row.get("tags") or []),
            is_active=row.get("is_active", True),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            latest_version=None,
        )

    def _row_to_version(self, row: Dict[str, Any]) -> schemas.AgentVersion:
        config = row.get("config") or {}
        return schemas.AgentVersion(
            id=row["id"],
            agent_id=row["agent_id"],
            version=row["version"],
            label=row.get("label"),
            created_by=row.get("created_by"),
            config=schemas.AgentVersionConfig(
                provider=config.get("provider", ""),
                model=config.get("model", ""),
                persona=config.get("persona") or {},
                prompt_template=config.get("prompt_template"),
                response_parameters=config.get("response_parameters") or {},
            ),
            prompt_template=row.get("prompt_template"),
            persona=row.get("persona") or {},
            response_parameters=row.get("response_params") or {},
            created_at=row["created_at"],
        )

    def _row_to_test(self, row: Dict[str, Any]) -> schemas.AgentTestRecord:
        return schemas.AgentTestRecord(
            id=row["id"],
            agent_id=row["agent_id"],
            agent_version_id=row.get("agent_version_id"),
            input_prompt=row["input_prompt"],
            response=row.get("response") or {},
            metrics=row.get("metrics") or {},
            status=row.get("status", "success"),
            channel=row.get("channel"),
            ran_at=row["ran_at"],
        )

    def _row_to_channel_config(self, row: Dict[str, Any]) -> schemas.ChannelConfig:
        return schemas.ChannelConfig(
            channel=row["channel"],
            is_enabled=row.get("is_enabled", True),
            webhook_secret=row.get("webhook_secret"),
            credentials=row.get("credentials") or {},
            settings=row.get("settings") or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )



# ---------------------------------------------------------------------------
# In-memory repository (useful for testing and sandbox environments)


class InMemoryAgentRepository(AgentRepository):
    def __init__(self) -> None:
        self._agents: Dict[int, schemas.AgentDetail] = {}
        self._versions: Dict[int, List[schemas.AgentVersion]] = {}
        self._tests: Dict[int, List[schemas.AgentTestRecord]] = {}
        self._agent_id_seq = 1
        self._version_id_seq = 1
        self._test_id_seq = 1

    def list_agents(self) -> List[schemas.Agent]:
        agents = [schemas.Agent(**agent.model_dump()) for agent in self._agents.values()]
        for agent in agents:
            versions = self._versions.get(agent.id, [])
            agent.latest_version = versions[-1] if versions else None
        agents.sort(key=lambda a: a.name)
        return agents

    def get_agent(
        self, agent_id: int, *, include_versions: bool = False, include_tests: bool = False
    ) -> Optional[schemas.AgentDetail]:
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        clone = schemas.AgentDetail(**agent.model_dump())
        if include_versions:
            clone.versions = list(self._versions.get(agent_id, []))
            clone.latest_version = clone.versions[-1] if clone.versions else None
        else:
            versions = self._versions.get(agent_id, [])
            clone.latest_version = versions[-1] if versions else None
        if include_tests:
            clone.tests = list(self._tests.get(agent_id, []))
        return clone

    def get_agent_by_slug(
        self, slug: str, *, include_versions: bool = False, include_tests: bool = False
    ) -> Optional[schemas.AgentDetail]:
        for agent in self._agents.values():
            if agent.slug == slug:
                source = agent
                break
        else:
            return None
        clone = schemas.AgentDetail(**source.model_dump())
        if include_versions:
            clone.versions = list(self._versions.get(source.id, []))
            clone.latest_version = clone.versions[-1] if clone.versions else None
        else:
            versions = self._versions.get(source.id, [])
            clone.latest_version = versions[-1] if versions else None
        if include_tests:
            clone.tests = list(self._tests.get(source.id, []))
        return clone

    def create_agent(self, payload: schemas.AgentCreate) -> schemas.Agent:
        agent_id = self._agent_id_seq
        self._agent_id_seq += 1
        now = datetime.now(timezone.utc)
        slug = self._make_unique_slug(payload.name)
        detail = schemas.AgentDetail(
            id=agent_id,
            slug=slug,
            name=payload.name,
            description=payload.description,
            provider=payload.provider,
            model=payload.model,
            persona=payload.persona,
            prompt_template=payload.prompt_template,
            response_parameters=payload.response_parameters,
            deployment_metadata=payload.deployment_metadata or {},
            tags=payload.tags or [],
            is_active=payload.is_active,
            created_at=now,
            updated_at=now,
            versions=[],
            tests=[],
            latest_version=None,
        )
        self._agents[agent_id] = detail
        return schemas.Agent(**detail.model_dump())

    def _make_unique_slug(self, name: str, exclude_id: Optional[int] = None) -> str:
        base = _slugify(name)
        slug = base
        suffix = 1
        used = {agent.slug for aid, agent in self._agents.items() if aid != exclude_id}
        while slug in used:
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def update_agent(self, agent_id: int, payload: schemas.AgentUpdate) -> schemas.Agent:
        agent = self._agents.get(agent_id)
        if not agent:
            raise AgentNotFoundError
        data = _model_dump(payload)
        for key, value in data.items():
            if key == "persona":
                agent.persona = value
            elif key == "prompt_template":
                agent.prompt_template = value
            elif key == "response_parameters":
                agent.response_parameters = value
            elif key == "deployment_metadata":
                agent.deployment_metadata = value or {}
            elif key == "tags":
                agent.tags = value or []
            elif key == "is_active":
                agent.is_active = bool(value)
            elif key == "name":
                agent.name = value
                agent.slug = self._make_unique_slug(value, exclude_id=agent_id)
            elif key == "description":
                agent.description = value
            elif key == "provider":
                agent.provider = value
            elif key == "model":
                agent.model = value
        agent.updated_at = datetime.now(timezone.utc)
        self._agents[agent_id] = agent
        return schemas.Agent(**agent.model_dump())

    def delete_agent(self, agent_id: int) -> None:
        self._agents.pop(agent_id, None)
        self._versions.pop(agent_id, None)
        self._tests.pop(agent_id, None)

    def create_version(self, agent_id: int, payload: schemas.AgentVersionCreate) -> schemas.AgentVersion:
        versions = self._versions.setdefault(agent_id, [])
        version_number = versions[-1].version + 1 if versions else 1
        version = schemas.AgentVersion(
            id=self._version_id_seq,
            agent_id=agent_id,
            version=version_number,
            label=payload.label,
            created_by=payload.created_by,
            config=payload.config,
            prompt_template=payload.config.prompt_template,
            persona=payload.config.persona,
            response_parameters=payload.config.response_parameters,
            created_at=datetime.now(timezone.utc),
        )
        self._version_id_seq += 1
        versions.append(version)
        agent = self._agents.get(agent_id)
        if agent:
            agent.latest_version = version
        return version

    def list_versions(self, agent_id: int) -> List[schemas.AgentVersion]:
        return list(self._versions.get(agent_id, []))

    def latest_version(self, agent_id: int) -> Optional[schemas.AgentVersion]:
        versions = self._versions.get(agent_id, [])
        return versions[-1] if versions else None

    def record_test(self, payload: schemas.AgentTestRecordCreate) -> schemas.AgentTestRecord:
        record = schemas.AgentTestRecord(
            id=self._test_id_seq,
            agent_id=payload.agent_id,
            agent_version_id=payload.agent_version_id,
            input_prompt=payload.input_prompt,
            response=payload.response,
            metrics=payload.metrics,
            status=payload.status,
            channel=payload.channel,
            ran_at=datetime.now(timezone.utc),
        )
        self._test_id_seq += 1
        self._tests.setdefault(payload.agent_id, []).insert(0, record)
        return record

    def list_tests(self, agent_id: int, limit: int = 20) -> List[schemas.AgentTestRecord]:
        return list(self._tests.get(agent_id, []))[:limit]

    def update_deployment_metadata(self, agent_id: int, metadata: Dict[str, Any]) -> schemas.Agent:
        agent = self._agents.get(agent_id)
        if not agent:
            raise AgentNotFoundError
        agent.deployment_metadata = metadata
        agent.updated_at = datetime.now(timezone.utc)
        return schemas.Agent(**agent.model_dump())


# ---------------------------------------------------------------------------
# Service factory helpers


def create_postgres_service(connection: psycopg.Connection) -> AgentService:
    repository = PostgresAgentRepository(connection)
    return AgentService(repository)


@contextmanager
def service_context_from_dsn(dsn: str) -> Iterator[AgentService]:
    conn = psycopg.connect(dsn)
    try:
        service = create_postgres_service(conn)
        yield service
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
