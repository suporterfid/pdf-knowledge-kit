# Architecture Overview

This document captures the relationships between the agent-oriented Python services and the React context providers that coordinate frontend state.

## Backend – Agent Orchestration (`app/agents`)

```
Agents Service Layer
├── AgentService (service.py)
│   ├── AgentRepository protocol (service.py)
│   │   └── PostgresAgentRepository – psycopg-backed CRUD over agents, versions, tests, and channel configs (service.py)
│   ├── ProviderRegistry – resolves ProviderCredentials from overrides/env (providers.py)
│   │   └── ProviderCredentials – builds HTTP headers for downstream LLM APIs (providers.py)
│   ├── PromptTemplateStore – persona/provider template resolution & rendering (prompts.py)
│   ├── ResponseParameterStore – provider default + override merge (responses.py)
│   └── Utility helpers
│       ├── _normalise_create_payload / _normalise_update_payload – enrich persistence payloads (service.py)
│       └── _simulate_model_response – sandboxed test output generator (service.py)
└── Schemas Module (app/agents/schemas.py, not shown) – shared Pydantic models consumed across the layer
```

- **AgentService** coordinates CRUD, versioning, test execution, deployment metadata, and channel configuration by combining repository persistence with provider/prompt/response helpers.【F:app/agents/service.py†L101-L310】
- **PostgresAgentRepository** satisfies the `AgentRepository` protocol via SQL statements using a psycopg connection wrapper, translating rows into schema objects and vice versa.【F:app/agents/service.py†L394-L796】
- **ProviderRegistry** supplies API credentials for LLM providers, either from injected overrides or environment variables, while `ProviderCredentials` materialises the header payloads expected by downstream calls.【F:app/agents/providers.py†L9-L74】
- **PromptTemplateStore** merges built-in persona templates with optional overrides and resolves/render prompts based on persona/provider combinations.【F:app/agents/prompts.py†L7-L60】
- **ResponseParameterStore** keeps provider defaults and merges arbitrary overrides so AgentService can persist coherent response parameter payloads.【F:app/agents/responses.py†L7-L39】

## Frontend – React Context Graph (`frontend/src`)

```
Context Providers
├── ApiKeyProvider (apiKey.tsx)
│   ├── useApiKey – exposes stored key & mutators
│   └── useApiFetch – wraps fetch with API key header & toast-based auth errors
├── ConfigProvider (config.tsx)
│   └── Depends on useApiFetch to hydrate runtime UI config from /api/config
├── ChatProvider (chat.tsx)
│   ├── Depends on useConfig (from ConfigProvider) for upload limits
│   ├── Depends on useApiFetch (from ApiKeyProvider) for chat/upload calls
│   └── Streams SSE responses, manages localStorage session state, retry/cancel controls
└── ThemeProvider (theme.tsx)
    └── Manages CSS variables/localStorage for light vs. dark themes
```

- **ApiKeyProvider** centralises API key persistence, exposes typed hooks, and wraps `fetch` to decorate requests and surface auth errors via toasts.【F:frontend/src/apiKey.tsx†L1-L65】
- **ConfigProvider** layers server-provided branding/upload settings over defaults after retrieving them with `useApiFetch`, making them available app-wide via context.【F:frontend/src/config.tsx†L1-L43】
- **ChatProvider** orchestrates conversational state, file uploads, and streaming SSE responses, depending on both the configuration and API key contexts to enforce limits and authenticate network requests.【F:frontend/src/chat.tsx†L1-L270】
- **ThemeProvider** toggles between light/dark palettes by mutating document-level CSS variables and persisting the choice in `localStorage`.【F:frontend/src/theme.tsx†L1-L64】

## Multi-tenancy & Row Level Security

The system implements tenant isolation using PostgreSQL Row Level Security (RLS):

### Architecture Overview

```
Request Flow with Tenant Isolation
├── TenantContextMiddleware (app/core/tenant_middleware.py)
│   ├── Extracts JWT from Authorization header
│   ├── Validates token and extracts tenant_id
│   ├── Sets PostgreSQL session variable: SET app.tenant_id = '<tenant_id>'
│   └── Populates request.state.tenant_id and context var
├── RAG Query (app/rag.py)
│   ├── Executes standard SQL query (no WHERE tenant_id clause)
│   └── RLS policies automatically filter results by app.tenant_id
└── Ingestion (app/ingestion/storage.py)
    ├── Reads tenant_id from context var (get_current_tenant_id)
    └── Sets organization_id on documents and chunks
```

### RLS Implementation

**Database Schema (migration 011_add_rls_for_multi_tenancy.sql)**:
- `documents.organization_id` → UUID foreign key to `organizations.id`
- `chunks.organization_id` → UUID foreign key to `organizations.id`
- RLS policies enabled on both tables
- Policies filter by: `organization_id::text = current_setting('app.tenant_id', true)`
- Backward compatible: allows queries when `app.tenant_id` is NULL/empty

**Benefits**:
- **Automatic Enforcement**: Database enforces isolation, not application code
- **No Query Changes**: Existing SELECT statements work unchanged
- **Defense in Depth**: Even if application logic fails, database prevents cross-tenant access
- **Performance**: RLS filters applied at query plan level, uses indexes efficiently

**Tenant Context Flow**:
1. `TenantContextMiddleware` validates JWT → extracts `tenant_id`
2. Middleware executes: `SELECT set_config('app.tenant_id', '<uuid>', true)`
3. PostgreSQL session variable persists for request duration
4. All queries automatically filtered by RLS policies
5. Middleware resets: `RESET app.tenant_id` after response

## New Modules Since Last Update

- **RLS Migration (migrations/011_add_rls_for_multi_tenancy.sql)** – Adds `organization_id` columns to documents/chunks tables, enables RLS policies
- **RLS Tests (tests/test_rls_tenant_isolation.py)** – Integration tests verifying tenant isolation with various query patterns
