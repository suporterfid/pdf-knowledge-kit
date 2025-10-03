# API Reference

This document describes all FastAPI endpoints exposed by the PDF Knowledge Kit backend along with their authentication requirements and the Pydantic models that shape request and response payloads.

## Authentication and Roles

Most administrative routers protect endpoints with the `require_role` dependency, which validates an `X-API-Key` header against role-specific keys defined in the environment. Roles are hierarchical (`viewer` < `operator` < `admin`); requests missing a key, supplying an unknown key, or authenticating with insufficient privileges receive `401` or `403` responses.【F:app/security/auth.py†L1-L90】

## Core Application (`app.main`)

### Endpoint overview

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Lightweight health probe. |
| GET | `/api/config` | Returns frontend configuration values from the environment. |
| POST | `/api/upload` | Accepts a single PDF upload and returns a temporary download URL. |
| POST | `/api/ask` | Answers a question using retrieval augmented generation. |
| POST | `/api/chat` | Starts an SSE chat stream (rate limited). |
| GET | `/api/chat` | GET variant of the SSE chat stream without file uploads. |

#### GET `/api/health`
- **Auth:** None
- **Description:** Returns a static JSON payload indicating service health.【F:app/main.py†L178-L181】
- **Responses:**
  | Status | Body |
  | --- | --- |
  | 200 | `{ "status": "ok" }`

#### GET `/api/config`
- **Auth:** None
- **Description:** Surfaces selected configuration values (brand name, upload limits) for the frontend.【F:app/main.py†L184-L195】
- **Responses:** 200 with JSON containing `BRAND_NAME`, `POWERED_BY_LABEL`, `LOGO_URL`, `UPLOAD_MAX_SIZE`, and `UPLOAD_MAX_FILES`.

#### POST `/api/upload`
- **Auth:** None
- **Description:** Stores a single PDF upload (content type validated against `UPLOAD_ALLOWED_MIME_TYPES`) and schedules deletion after the configured TTL.【F:app/main.py†L198-L219】
- **Request Body:** Multipart form-data with file field `file` (`UploadFile`). Files exceeding `UPLOAD_MAX_SIZE` or with disallowed MIME types return `400` errors.【F:app/main.py†L208-L212】【F:app/main.py†L253-L255】
- **Responses:** 200 with `{ "url": "/uploads/<generated-name>" }`.

#### POST `/api/ask`
- **Auth:** None
- **Description:** Accepts an `AskRequest` payload and returns an answer plus retrieval metadata.【F:app/main.py†L222-L231】
- **Request Body:** `AskRequest`
  | Field | Type | Notes |
  | --- | --- | --- |
  | `q` | `str` | Question text.【F:app/main.py†L127-L130】
  | `k` | `int` | Number of documents to retrieve (default `5`).【F:app/main.py†L127-L130】
- **Responses:** 200 with `{ "answer": str, "sources": list, "used_llm": bool }`.

#### POST `/api/chat`
- **Auth:** None (rate limited to 5 requests/minute per client IP).
- **Description:** Starts a streaming chat response over Server-Sent Events, optionally including uploaded PDFs or references to prior uploads.【F:app/main.py†L234-L257】【F:app/main.py†L270-L320】
- **Request Body:** `multipart/form-data`
  | Field | Type | Required | Notes |
  | --- | --- | --- | --- |
  | `q` | string (form) | Yes | Chat prompt; >`CHAT_MAX_MESSAGE_LENGTH` yields `400`.|【F:app/main.py†L238-L251】
  | `k` | integer (form) | No (default `5`) | Retrieval depth.【F:app/main.py†L239】
  | `attachments` | stringified JSON array | No | Metadata for previously uploaded files.【F:app/main.py†L240-L256】
  | `sessionId` | string (form) | Yes | Must be ≤ `SESSION_ID_MAX_LENGTH` or `400` raised.【F:app/main.py†L241-L266】
  | `files` | list of `UploadFile` | No | Each file must be an allowed MIME type or `400` is returned.【F:app/main.py†L242-L256】
- **Responses:** `text/event-stream` streaming tokens. Validation failures return `400`.

#### GET `/api/chat`
- **Auth:** None (same rate limiting as POST variant).
- **Description:** Streaming chat endpoint without file uploads.【F:app/main.py†L259-L267】
- **Query Parameters:**
  | Name | Type | Required | Notes |
  | --- | --- | --- | --- |
  | `q` | string | Yes | Prompt; subject to the same length validation.【F:app/main.py†L261-L265】
  | `k` | integer | No (default `5`) | Retrieval depth.【F:app/main.py†L261】
  | `sessionId` | string | No | Must respect max length when provided.【F:app/main.py†L261-L266】
- **Responses:** `text/event-stream` streaming tokens.

## Auth Router (`/api/auth`)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/auth/roles` | Echoes the caller's resolved role; requires at least `viewer`. |

#### GET `/api/auth/roles`
- **Auth:** `X-API-Key` with `viewer` role or higher.【F:app/routers/auth_api.py†L1-L10】【F:app/security/auth.py†L50-L90】
- **Responses:** 200 with `{ "roles": ["<caller-role>"] }`.

## Admin Ingestion Router (`/api/admin/ingest`)

All endpoints require an API key; list views require `viewer`, mutating actions require `operator` unless noted.【F:app/routers/admin_ingest_api.py†L184-L624】 Models referenced below come from `app.ingestion.models`.【F:app/ingestion/models.py†L1-L674】

### Endpoint overview

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| POST | `/local` | operator | Start ingestion for a local filesystem path. |
| POST | `/reindex_all` | operator | Reindex every active source. |
| POST | `/url` | operator | Ingest a single URL. |
| POST | `/urls` | operator | Ingest multiple URLs. |
| POST | `/database` | operator | Launch database connector ingestion. |
| POST | `/api` | operator | Launch REST/API connector ingestion. |
| POST | `/transcription` | operator | Launch audio/video transcription ingestion. |
| GET | `/connector_definitions` | viewer | List connector definitions. |
| POST | `/connector_definitions` | operator | Create a connector definition. |
| GET | `/connector_definitions/{definition_id}` | viewer | Retrieve a connector definition. |
| PUT | `/connector_definitions/{definition_id}` | operator | Update a connector definition. |
| DELETE | `/connector_definitions/{definition_id}` | operator | Delete a connector definition. |
| GET | `/jobs` | viewer | List ingestion jobs. |
| GET | `/jobs/{job_id}` | viewer | Fetch a specific job. |
| POST | `/jobs/{job_id}/cancel` | operator | Cancel an in-flight job. |
| POST | `/jobs/{job_id}/rerun` | operator | Rerun a prior job. |
| GET | `/jobs/{job_id}/logs` | viewer | Read a slice of job logs. |
| GET | `/sources` | viewer | List sources. |
| POST | `/sources` | operator | Create or upsert a source. |
| PUT | `/sources/{source_id}` | operator | Update a source. |
| DELETE | `/sources/{source_id}` | operator | Soft-delete a source. |
| POST | `/sources/{source_id}/reindex` | operator | Trigger reindex for a source. |

#### POST `/api/admin/ingest/local`
- **Request Body:** `LocalIngestRequest` (`path: str`, `use_ocr: bool = False`, `ocr_lang: Optional[str]`).【F:app/ingestion/models.py†L327-L333】
- **Responses:** 200 with `JobCreated` (`job_id: UUID`).【F:app/routers/admin_ingest_api.py†L184-L193】【F:app/ingestion/models.py†L462-L466】 Missing or misconfigured OCR paths propagate `404`/`500` from ingestion service.

#### POST `/api/admin/ingest/reindex_all`
- **Description:** Iterates all active sources and enqueues reindex jobs; returns the IDs created.【F:app/routers/admin_ingest_api.py†L195-L205】
- **Responses:** 200 with `ListResponse[JobCreated]` containing each job ID.【F:app/ingestion/models.py†L622-L626】 If no sources are active, `items` is empty.

#### POST `/api/admin/ingest/url`
- **Request Body:** `UrlIngestRequest` (`url: HttpUrl`).【F:app/ingestion/models.py†L335-L339】
- **Responses:** 200 with `JobCreated`. Raises `400` for invalid URLs via Pydantic validation.【F:app/routers/admin_ingest_api.py†L208-L214】

#### POST `/api/admin/ingest/urls`
- **Request Body:** `UrlsIngestRequest` (`urls: List[HttpUrl]`).【F:app/ingestion/models.py†L341-L344】
- **Responses:** 200 with `JobCreated`; invalid URLs raise validation errors.【F:app/routers/admin_ingest_api.py†L217-L223】

#### POST `/api/admin/ingest/database`
- **Request Body:** `DatabaseConnectorJobRequest`, including optional source linkage, connector definition reference, parameters, credentials, metadata, and sync state.【F:app/ingestion/models.py†L232-L309】 Database-specific parameters must supply at least one query.【F:app/routers/admin_ingest_api.py†L226-L265】【F:app/routers/admin_ingest_api.py†L112-L123】
- **Responses:** 200 with `JobCreated`. The route emits `400` if credentials are missing or parameters are incomplete and `404` if referenced sources/definitions are not found.【F:app/routers/admin_ingest_api.py†L226-L265】

#### POST `/api/admin/ingest/api`
- **Request Body:** `ApiConnectorJobRequest` (same base fields as above with REST-specific params). API connectors must define an endpoint or base URL.【F:app/ingestion/models.py†L197-L217】【F:app/routers/admin_ingest_api.py†L268-L307】
- **Responses:** 200 with `JobCreated`; validation errors mirror the database route.

#### POST `/api/admin/ingest/transcription`
- **Request Body:** `TranscriptionConnectorJobRequest` with audio/video metadata; the connector type is inferred from payload or definition.【F:app/ingestion/models.py†L299-L309】【F:app/routers/admin_ingest_api.py†L310-L356】 Missing provider metadata triggers `400` responses.【F:app/routers/admin_ingest_api.py†L112-L133】
- **Responses:** 200 with `JobCreated` or `404` when the source/definition cannot be located.【F:app/routers/admin_ingest_api.py†L310-L356】

#### Connector definition endpoints
- **Models:**
  - `ConnectorDefinition` encapsulates stored metadata, params, credential indicators, and timestamps.【F:app/ingestion/models.py†L492-L597】
  - `ConnectorDefinitionCreate`/`ConnectorDefinitionUpdate` enforce parameter requirements per source type.【F:app/ingestion/models.py†L540-L588】
- **Behavior:** `GET` supports filtering by `type`, pagination via `limit`/`offset`, and always hides credential payloads.【F:app/routers/admin_ingest_api.py†L359-L379】 Create/update/delete operations raise `404` for missing records and `500` for unexpected storage failures.【F:app/routers/admin_ingest_api.py†L381-L475】 Successful create/update requests return the persisted `ConnectorDefinition` payload.

#### Job management endpoints
- **Models:** `Job` captures lifecycle metadata; `JobStatus` enumerates `queued`, `running`, `succeeded`, `failed`, `canceled` states.【F:app/ingestion/models.py†L312-L607】 `JobLogSlice` returns textual log chunks with the next offset.【F:app/ingestion/models.py†L622-L635】
- **Behavior:**
  - `GET /jobs` optionally filters by `status` and paginates with `limit`/`offset`.【F:app/routers/admin_ingest_api.py†L477-L493】
  - `GET /jobs/{job_id}` returns a single `Job` or `404`.【F:app/routers/admin_ingest_api.py†L495-L503】
  - `POST /jobs/{job_id}/cancel` cancels then returns the updated job, or `404` if unknown.【F:app/routers/admin_ingest_api.py†L505-L513】
  - `POST /jobs/{job_id}/rerun` creates a new job (`JobCreated`) or returns `404`.【F:app/routers/admin_ingest_api.py†L516-L524】
  - `GET /jobs/{job_id}/logs` returns a `JobLogSlice`, supporting `offset` and `limit` query params.【F:app/routers/admin_ingest_api.py†L526-L535】

#### Source endpoints
- **Models:** `Source` captures connector metadata; `SourceCreate` and `SourceUpdate` enforce params/credential normalization per source type.【F:app/ingestion/models.py†L353-L455】【F:app/ingestion/models.py†L468-L488】 Supported `SourceType` values include local directories, URLs, database/API connectors, and audio/video transcripts.【F:app/ingestion/models.py†L18-L108】
- **Behavior:**
  - `GET /sources` filters by `active` and `type`, returning a paginated `ListResponse[Source]`.【F:app/routers/admin_ingest_api.py†L537-L554】
  - `POST /sources` upserts and returns the resulting `Source`. Validation errors surface from the model and database layer.【F:app/routers/admin_ingest_api.py†L556-L577】
  - `PUT /sources/{source_id}` updates a source; unknown IDs raise `404`.【F:app/routers/admin_ingest_api.py†L580-L604】
  - `DELETE /sources/{source_id}` soft-deletes the source (setting `active = False`) and returns the final state.【F:app/routers/admin_ingest_api.py†L606-L614】
  - `POST /sources/{source_id}/reindex` enqueues a reindex job and returns `JobCreated`, falling back to `404` when the source does not exist.【F:app/routers/admin_ingest_api.py†L617-L624】

## Agent Management Router (`/api/agents`)

All endpoints require API keys; viewer role for reads, operator for writes.【F:app/routers/agents.py†L54-L172】 Pydantic schemas reside in `app.agents.schemas`.【F:app/agents/schemas.py†L1-L188】

### Endpoint overview

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/api/agents` | viewer | List agents with pagination metadata (`items`, `total`). |
| GET | `/api/agents/providers` | viewer | List supported provider identifiers. |
| POST | `/api/agents` | operator | Create an agent (201 Created). |
| GET | `/api/agents/{agent_id}` | viewer | Retrieve full agent detail (including versions/tests). |
| PUT | `/api/agents/{agent_id}` | operator | Update agent fields. |
| DELETE | `/api/agents/{agent_id}` | operator | Delete an agent; returns confirmation message. |
| GET | `/api/agents/{agent_id}/versions` | viewer | List historical versions. |
| POST | `/api/agents/{agent_id}/versions` | operator | Create a new version (201 Created). |
| POST | `/api/agents/{agent_id}/test` | operator | Run a test invocation. |
| GET | `/api/agents/{agent_id}/tests` | viewer | List prior test records. |
| GET | `/api/agents/{agent_id}/channels` | viewer | List channel configurations. |
| GET | `/api/agents/{agent_id}/channels/{channel}` | viewer | Fetch a specific channel config. |
| PUT | `/api/agents/{agent_id}/channels/{channel}` | operator | Upsert a channel configuration. |
| DELETE | `/api/agents/{agent_id}/channels/{channel}` | operator | Delete a channel configuration. |
| POST | `/api/agents/{agent_id}/deploy` | operator | Trigger deployment workflow. |

### Key schemas
- `AgentCreate`/`AgentUpdate` capture mutable agent properties (name, provider, model, persona, metadata, tags, etc.).【F:app/agents/schemas.py†L10-L48】
- `AgentDetail` extends `Agent` with version/test collections.【F:app/agents/schemas.py†L71-L92】
- `AgentVersion` & `AgentVersionCreate` describe immutable version snapshots.【F:app/agents/schemas.py†L50-L103】
- `AgentTestRequest` and `AgentTestResponse` carry test inputs/outputs; `AgentTestRecord` logs executions.【F:app/agents/schemas.py†L110-L144】
- Channel management uses `ChannelConfig`, `ChannelConfigUpdate`, and `ChannelConfigList`.【F:app/agents/schemas.py†L158-L178】
- `AgentDeployRequest` and `AgentDeployResponse` shape deployment operations.【F:app/agents/schemas.py†L146-L153】

### Behavior notes
- All endpoints use a shared service context; unknown agents yield `404` responses from the service layer.【F:app/routers/agents.py†L33-L51】
- Create endpoints respond with `201 Created` status codes as declared on the route decorators.【F:app/routers/agents.py†L67-L114】
- Delete endpoints return `{ "message": "deleted" }`.【F:app/routers/agents.py†L92-L97】【F:app/agents/schemas.py†L180-L181】
- Channel endpoints normalize channel keys via the service; missing configs return `404` from the repository layer.【F:app/routers/agents.py†L134-L163】
- Deployment returns an `AgentDeployResponse`, mirroring `AgentDetail` semantics.【F:app/routers/agents.py†L165-L172】【F:app/agents/schemas.py†L152-L153】

## Conversation Router

Endpoints live under both `/api/agents/{agent_id}/...` and `/api/conversations/...` and require API keys (`viewer` for reads, `operator` for updates).【F:app/routers/conversations.py†L54-L113】 Schemas reside in `app.conversations.schemas`.【F:app/conversations/schemas.py†L10-L94】

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/api/agents/{agent_id}/conversations` | viewer | List recent conversations for an agent (default `limit=20`). |
| GET | `/api/agents/{agent_id}/conversations/dashboard` | viewer | Dashboard snapshot (aggregate stats and recent conversations). |
| GET | `/api/conversations/{conversation_id}` | viewer | Fetch a detailed conversation view. |
| POST | `/api/conversations/{conversation_id}/follow-up` | operator | Schedule a follow-up reminder. |
| POST | `/api/conversations/{conversation_id}/escalate` | operator | Escalate or resolve an escalation. |

### Key schemas
- `ConversationSummary`, `ConversationDetail`, and `ConversationList` capture conversation metadata, participants, and messages.【F:app/conversations/schemas.py†L30-L52】
- Follow-up and escalation requests/responses use `FollowUpRequest`, `EscalationRequest`, `FollowUpResponse`, and `EscalationResponse`.【F:app/conversations/schemas.py†L54-L70】
- Dashboard responses aggregate analytics through `ConversationDashboardPayload`.【F:app/conversations/schemas.py†L78-L94】

### Behavior notes
- Query parameters `limit` (defaults 20/10) are simple integers; out-of-range agent IDs or conversations propagate `404` responses from the service layer.【F:app/routers/conversations.py†L54-L113】
- Escalation endpoint accepts an optional `resolve` boolean query parameter; when `true` it calls the resolve flow instead of raising a new escalation.【F:app/routers/conversations.py†L101-L113】

## Feedback Router (`/api/feedback`)

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/feedback` | Persist user feedback about Q&A sessions. |

#### POST `/api/feedback`
- **Auth:** None
- **Request Body:** `FeedbackIn`
  | Field | Type | Notes |
  | --- | --- | --- |
  | `helpful` | `bool` | Marks the answer as helpful/unhelpful.【F:app/routers/feedback_api.py†L28-L63】
  | `question` | `str | None` | Optional question text.【F:app/routers/feedback_api.py†L28-L63】
  | `answer` | `str | None` | Optional answer text.【F:app/routers/feedback_api.py†L28-L63】
  | `sessionId` | `str | None` | Correlates feedback to a chat session.【F:app/routers/feedback_api.py†L28-L63】
  | `sources` | `Any | None` | Arbitrary metadata stored as JSONB.【F:app/routers/feedback_api.py†L28-L63】
- **Responses:** 200 with `FeedbackCreated` (`id: str`). Database connectivity issues emit `500` responses; invalid payloads surface via Pydantic validation.【F:app/routers/feedback_api.py†L36-L66】

## Webhooks Router

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/webhooks/{agent_slug}/{channel}` | Ingest messages from external channel-specific webhooks. |

#### POST `/api/webhooks/{agent_slug}/{channel}`
- **Auth:** Channel-specific signature verification performed by the adapter; invalid signatures yield `401`.【F:app/routers/webhooks.py†L80-L99】
- **Request Body:** Raw JSON payload; non-JSON bodies return `400`. Channel adapters may expect channel-specific structure.【F:app/routers/webhooks.py†L60-L85】
- **Behavior:**
  - Resolves the agent by slug and loads channel configuration; unknown agents or adapters raise `404`.【F:app/routers/webhooks.py†L67-L79】
  - Normalized messages are passed to the conversation service; when at least one message is processed, the endpoint returns a JSON body shaped like `MessageIngestResponse` (`conversation`, `processed_messages`). Otherwise, it responds with `202 Accepted` to acknowledge receipt.【F:app/routers/webhooks.py†L83-L100】【F:app/conversations/schemas.py†L44-L76】

