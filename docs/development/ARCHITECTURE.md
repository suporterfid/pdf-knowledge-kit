# System Architecture
> Generated: 2025-12-31

## Tech Stack

| Layer | Technology | Version | Documentation |
|-------|------------|---------|---------------|
| **Language (Backend)** | Python | 3.10+ | [python.org](https://python.org) |
| **Language (Frontend)** | TypeScript | 5.0+ | [typescriptlang.org](https://www.typescriptlang.org/) |
| **Framework (Backend)** | FastAPI | 0.110+ | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| **Framework (Frontend)** | React | 18.2 | [react.dev](https://react.dev) |
| **Build Tool (Frontend)** | Vite | 7.2+ | [vitejs.dev](https://vitejs.dev) |
| **Database** | PostgreSQL | 15+ | [postgresql.org](https://www.postgresql.org/) |
| **Vector Extension** | pgvector | 0.2.5+ | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) |
| **ORM** | SQLAlchemy | 2.0+ | [sqlalchemy.org](https://www.sqlalchemy.org/) |
| **Database Driver** | psycopg | 3.1+ | [psycopg.org](https://www.psycopg.org/) |
| **Embeddings** | fastembed | 0.7.3 | [qdrant.github.io/fastembed](https://qdrant.github.io/fastembed/) |
| **CSS Framework** | TailwindCSS | 3.4+ | [tailwindcss.com](https://tailwindcss.com) |
| **Testing (Backend)** | pytest | 8.0+ | [pytest.org](https://pytest.org) |
| **Testing (Frontend)** | Vitest | 4.0+ | [vitest.dev](https://vitest.dev) |
| **Container** | Docker | 24+ | [docker.com](https://www.docker.com/) |
| **Orchestration** | Docker Compose | 2.x | [docs.docker.com/compose](https://docs.docker.com/compose/) |
| **ASGI Server** | Uvicorn | 0.29+ | [uvicorn.org](https://www.uvicorn.org/) |
| **LLM Provider** | OpenAI (optional) | 1.0+ | [platform.openai.com](https://platform.openai.com) |
| **Metrics** | Prometheus | — | [prometheus.io](https://prometheus.io) |

## Directory Structure

```
pdf-knowledge-kit/
├── app/                        # Backend FastAPI application
│   ├── __init__.py
│   ├── __version__.py         # Version metadata (1.0.1)
│   ├── main.py                # FastAPI app bootstrap, routers, middleware
│   ├── rag.py                 # RAG retrieval engine (pgvector + BM25)
│   ├── nlp.py                 # Intent detection, sentiment analysis, entity extraction
│   ├── sse_utils.py           # Server-Sent Events streaming utilities
│   ├── app_logging.py         # Structured logging configuration
│   │
│   ├── agents/                # Agent orchestration system
│   │   ├── service.py         # CRUD, versioning, testing, deployment
│   │   ├── providers.py       # LLM provider credential management
│   │   ├── prompts.py         # Template resolution
│   │   ├── responses.py       # Response parameter defaults
│   │   ├── repository.py      # Data access layer (protocol + Postgres impl)
│   │   └── schemas.py         # Pydantic models for API contracts
│   │
│   ├── channels/              # Communication channel adapters
│   │   ├── base.py            # Abstract adapter interface
│   │   ├── whatsapp.py        # Meta WhatsApp Business API
│   │   └── telegram.py        # Telegram Bot API
│   │
│   ├── conversations/         # Multi-channel conversation management
│   │   ├── service.py         # Message processing, NLP enrichment, escalation
│   │   ├── repository.py      # PostgreSQL persistence layer
│   │   ├── models.py          # Business logic models
│   │   └── schemas.py         # Conversation, participant, message schemas
│   │
│   ├── core/                  # Core infrastructure
│   │   ├── auth.py            # JWT token validation (tenant-scoped)
│   │   ├── db.py              # Tenant-aware database connection helpers
│   │   ├── tenant_context.py  # ContextVar-based tenant scoping
│   │   └── tenant_middleware.py # Request-scoped tenant extraction, RLS setup
│   │
│   ├── ingestion/             # Document ingestion pipeline
│   │   ├── service.py         # High-level orchestration, schema management
│   │   ├── storage.py         # Database persistence for sources, documents, chunks
│   │   ├── chunking.py        # Text chunking with overlap (500 chars, 50 overlap)
│   │   ├── runner.py          # Thread pool executor for async job processing
│   │   ├── parsers/           # Document format parsers
│   │   │   ├── pdf.py         # PDF extraction (with OCR support via tesseract)
│   │   │   ├── markdown.py    # Markdown parsing
│   │   │   ├── html.py        # HTML parsing (BeautifulSoup)
│   │   │   ├── docx.py        # DOCX parsing
│   │   │   └── xlsx.py        # XLSX parsing
│   │   └── connectors/        # Remote data source connectors
│   │       ├── sql.py         # SQL database connector
│   │       ├── rest.py        # REST API connector
│   │       └── transcription.py # Audio/video transcription (Whisper/AWS)
│   │
│   ├── migrations/            # Alembic-style database migrations
│   │   ├── 001_*.py
│   │   └── 013_*.py           # 13 total migrations
│   │
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── tenant.py          # Organizations, Users, Invites, RefreshTokens
│   │   └── session.py         # Database engine and session factory
│   │
│   ├── routers/               # FastAPI route handlers
│   │   ├── admin_ingest_api.py # Source management, ingestion jobs, logs
│   │   ├── agents.py          # Agent CRUD, versioning, testing
│   │   ├── auth_api.py        # Role verification endpoint
│   │   ├── chat_sessions.py   # Session persistence
│   │   ├── conversations.py   # Conversation queries, follow-ups, escalations
│   │   ├── feedback_api.py    # User feedback collection
│   │   ├── tenant_accounts.py # Multi-tenant account management
│   │   └── webhooks.py        # Webhook ingestion (WhatsApp/Telegram)
│   │
│   ├── security/              # Authentication & authorization
│   │   ├── auth.py            # FastAPI dependencies for RBAC (viewer/operator/admin)
│   │   ├── passwords.py       # Argon2 password hashing
│   │   └── tokens.py          # JWT generation and validation
│   │
│   └── static/                # Frontend build artifacts (served by FastAPI)
│       ├── index.html
│       └── assets/
│
├── frontend/                  # React SPA
│   ├── src/
│   │   ├── main.tsx           # React 18 entry point
│   │   ├── App.tsx            # React Router configuration
│   │   ├── ChatPage.tsx       # Main chat interface
│   │   ├── theme.tsx          # Dark/light theme configuration
│   │   ├── config.tsx         # Runtime configuration (brand, logo, etc.)
│   │   │
│   │   ├── auth/              # Authentication system
│   │   │   ├── AuthProvider.tsx # JWT + refresh token logic, auto-refresh
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   └── RequireAuth.tsx # Auth guard component
│   │   │
│   │   ├── admin/             # Admin dashboard
│   │   │   ├── AdminApp.tsx   # Admin router
│   │   │   ├── Dashboard.tsx
│   │   │   ├── IngestLocal.tsx # File upload UI
│   │   │   ├── IngestUrl.tsx  # URL ingestion UI
│   │   │   ├── JobDetail.tsx  # Job monitoring
│   │   │   ├── Sources.tsx    # Source management
│   │   │   └── AgentBuilder.tsx # Agent configuration UI
│   │   │
│   │   ├── components/        # Shared React components
│   │   │   ├── Composer.tsx   # Message input + file upload
│   │   │   ├── ConversationPane.tsx # Message list
│   │   │   ├── ErrorBanner.tsx # Error handling UI
│   │   │   ├── Footer.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── Message.tsx    # Single message rendering
│   │   │   ├── Sidebar.tsx    # Conversation history
│   │   │   └── SourcesList.tsx # RAG sources display
│   │   │
│   │   ├── hooks/             # Custom React hooks
│   │   │   └── useAuth.ts     # Auth context hook
│   │   │
│   │   └── chat.tsx           # useChat hook + SSE streaming logic
│   │
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
│
├── migrations/                # SQL migration scripts
│   ├── 001_create_tables.sql
│   └── 013_*.sql              # 13 migrations
│
├── tests/                     # Backend test suite (pytest)
│   ├── conftest.py            # Shared fixtures (tenant_auth, app_factory)
│   ├── test_rag.py
│   ├── test_ingest_*.py
│   ├── test_agents_*.py
│   ├── test_auth_*.py
│   ├── test_rls_*.py
│   └── ... (39 test files)
│
├── tools/                     # CLI utilities
│   ├── register_connector.py # Connector registration helper
│   └── print_log_config.py   # Log configuration inspector
│
├── docs/                      # Documentation (AI agent development tracking)
│   ├── development/
│   │   ├── STATUS.md          # Current project status
│   │   ├── ARCHITECTURE.md    # This file
│   │   ├── ROADMAP.md         # Development roadmap
│   │   ├── BACKLOG.md         # Prioritized task backlog
│   │   ├── TECHNICAL_DEBT.md  # Technical debt registry
│   │   └── CHANGELOG.md       # Detailed changelog
│   ├── prompts/
│   │   ├── 01-ANALYSIS.md     # Re-analysis prompt
│   │   ├── 02-UPDATE.md       # Documentation update prompt
│   │   └── 03-IMPLEMENT.md    # Implementation prompt
│   └── TECH_STACK_STANDARDS.md # Coding conventions and standards
│
├── schema.sql                 # Idempotent base schema (RLS, pgvector)
├── ingest.py                  # Legacy CLI for local ingestion
├── query.py                   # CLI for RAG queries
├── embedding.py               # Standalone embedding utilities
├── seed.py                    # Database seeding for development
├── docker-compose.yml         # Production orchestration
├── docker-compose.dev.yml     # Development orchestration
├── Dockerfile                 # Production image
├── Dockerfile.dev             # Development image (with debugpy)
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
├── pyproject.toml             # Black, Ruff, Mypy, Bandit configuration
├── pytest.ini                 # Pytest configuration
├── .env.example               # Environment variable template
└── AGENTS.md                  # Root-level AI agent instructions

```

## Core Modules

### Backend: `app/main.py` (529 lines)
- **Purpose**: FastAPI application bootstrap and HTTP endpoint orchestration
- **Location**: `/home/user/pdf-knowledge-kit/app/main.py:1-529`
- **Dependencies**: FastAPI, SlowAPI (rate limiting), Prometheus instrumentation, tenant middleware
- **Public Interface**:
  - `GET /api/health` — Health check endpoint
  - `GET /api/version` — Version information (build date, commit SHA)
  - `GET /api/config` — Frontend configuration (brand, logo, feature flags)
  - `POST /api/upload` — Temporary file upload (PDF, rate-limited to 5/min)
  - `POST /api/ask` — RAG query endpoint (JSON response)
  - `GET /api/chat` — SSE streaming chat endpoint
  - `GET /api/metrics` — Prometheus metrics
  - Static file serving at `/`

### Backend: `app/rag.py` (186 lines)
- **Purpose**: Retrieval-Augmented Generation engine with vector similarity search
- **Location**: `/home/user/pdf-knowledge-kit/app/rag.py:117-186`
- **Dependencies**: psycopg, fastembed (paraphrase-multilingual-MiniLM-L12-v2-cls), rank-bm25
- **Public Interface**:
  - `build_context(question, k=5, pre_k=20, tenant_id)` — Returns context + sources
  - Flow: Embed query → Vector search (pgvector L2) → BM25 reranking → Return top k chunks
- **Performance**: Typical query latency <100ms for 10K chunks

### Backend: `app/ingestion/service.py` (1,238 lines)
- **Purpose**: Document ingestion pipeline orchestration and job management
- **Location**: `/home/user/pdf-knowledge-kit/app/ingestion/service.py`
- **Dependencies**: ThreadPoolExecutor, parsers (PDF/MD/DOCX/etc.), fastembed, storage layer
- **Public Interface**:
  - `ingest_local(docs_dir, tenant_id, enable_ocr=False)` — Local file ingestion
  - `ingest_url(url, tenant_id)` — URL ingestion
  - `ingest_connector(definition, tenant_id)` — Connector-based ingestion
  - `get_job_status(job_id)` — Job status query
  - `cancel_job(job_id)` — Job cancellation
- **Background Processing**: Jobs run in thread pool, status updates written to DB

### Backend: `app/agents/service.py` (796 lines)
- **Purpose**: Agent lifecycle management (CRUD, versioning, testing, deployment)
- **Location**: `/home/user/pdf-knowledge-kit/app/agents/service.py:93-310`
- **Dependencies**: AgentRepository (protocol), LLM provider clients, prompt templates
- **Public Interface**:
  - `create_agent(definition, tenant_id)` — Create new agent
  - `update_agent(agent_id, updates)` — Update agent configuration
  - `deploy_version(agent_id, version)` — Deploy specific version to channel
  - `test_agent(agent_id, test_input)` — Test agent with sample input
  - `list_agents(tenant_id, filters)` — List agents with filtering

### Backend: `app/core/tenant_middleware.py` (159 lines)
- **Purpose**: Request-scoped tenant extraction and Row-Level Security enforcement
- **Location**: `/home/user/pdf-knowledge-kit/app/core/tenant_middleware.py:27-159`
- **Dependencies**: JWT validation, ContextVar, psycopg
- **Public Interface**: ASGI middleware (transparent to routes)
- **Flow**: Extract JWT → Validate signature → Set `app.tenant_id` in PostgreSQL session → Execute request

### Frontend: `src/auth/AuthProvider.tsx` (578 lines)
- **Purpose**: JWT authentication state management with auto-refresh
- **Location**: `/home/user/pdf-knowledge-kit/frontend/src/auth/AuthProvider.tsx:1-578`
- **Dependencies**: React Context API, localStorage, fetch API
- **Public Interface**:
  - `useAuth()` hook → `{user, tokens, login(), logout(), register(), switchTenant()}`
  - Auto-refresh: Refreshes JWT 5 seconds before expiry
  - Rate limiting: Max 3 refresh attempts, 5-second throttle

### Frontend: `src/chat.tsx` (useChat hook)
- **Purpose**: SSE streaming chat state management
- **Location**: `/home/user/pdf-knowledge-kit/frontend/src/chat.tsx`
- **Dependencies**: EventSource, React useState/useEffect
- **Public Interface**:
  - `useChat()` → `{messages, sendMessage(), isStreaming, error, retry()}`
  - Automatic reconnection with exponential backoff
  - Buffer management for token-by-token streaming

## Data Flow

### Ingestion Pipeline

```
User Upload (local/URL/connector)
  ↓
POST /api/admin/ingest/{type}
  ↓
IngestionService.ingest_*() creates Job (PENDING)
  ↓
ThreadPoolExecutor picks up job → status: RUNNING
  ↓
1. Parse document (PDF → text via pypdf or tesseract OCR)
2. Chunk text (500 chars, 50 char overlap)
3. Generate embeddings (fastembed, 384-dim vectors)
4. Upsert to PostgreSQL:
   - INSERT INTO sources (url, type, tenant_id)
   - INSERT INTO documents (source_id, title, content)
   - INSERT INTO chunks (document_id, text, embedding)
  ↓
Job status: SUCCEEDED (or FAILED with error log)
  ↓
Frontend polls GET /api/admin/ingest/jobs/{job_id}
```

### RAG Query Pipeline

```
User question → POST /api/ask or GET /api/chat
  ↓
rag.build_context(question, k=5, tenant_id)
  ↓
1. Embed question (fastembed, 384-dim vector)
2. Vector similarity search (pgvector):
   SELECT id, text, content, url
   FROM chunks c
   JOIN documents d ON c.document_id = d.id
   JOIN sources s ON d.source_id = s.id
   WHERE c.organization_id = app.current_tenant_id()
   ORDER BY embedding <-> $1  -- L2 distance
   LIMIT 20  -- pre_k
3. BM25 reranking (lexical scoring):
   - Tokenize chunks and question
   - Compute BM25 scores
   - Select top k=5 chunks
4. Concatenate chunks → context string
  ↓
_answer_with_context(question, context)
  ↓
If OPENAI_API_KEY configured:
  - OpenAI ChatCompletion with streaming
  - System prompt + context + user question
  - Stream tokens via SSE (/api/chat) or return JSON (/api/ask)
Else:
  - Deterministic response: "Based on the context: [context]"
  ↓
Frontend displays answer + sources (with URLs + highlights)
```

### Webhook Processing (Conversations)

```
WhatsApp/Telegram webhook → POST /api/webhooks/{agent_slug}/{channel}
  ↓
1. Verify signature:
   - WhatsApp: HMAC-SHA256 (X-Hub-Signature-256)
   - Telegram: Secret token (X-Telegram-Bot-Api-Secret-Token)
2. Parse payload via ChannelAdapter (normalize message format)
  ↓
ConversationService.process_incoming_message()
  ↓
1. Get or create conversation (key: channel + external_id)
2. Get or create participant (user phone/username)
3. NLP analysis (app/nlp.py):
   - Intent detection (complaint, cancellation, support, callback)
   - Sentiment analysis (positive, negative, neutral)
   - Entity extraction (email, amounts, datetime)
4. Store message in DB with NLP metadata
5. Evaluate escalation rules (e.g., negative sentiment → human handoff)
6. Schedule follow-up if needed
  ↓
Return 202 Accepted or MessageIngestResponse
  ↓
Agent responds via channel API (async, not blocking webhook)
```

## External Integrations

### Databases
| Service | Purpose | Config Location |
|---------|---------|-----------------|
| PostgreSQL 15+ with pgvector | Primary data store (sources, chunks, tenants, users) | `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` |

### LLM Providers (Optional)
| Service | Purpose | Config Location |
|---------|---------|-----------------|
| OpenAI API | GPT-4/GPT-3.5 for chat completions | `OPENAI_API_KEY`, `OPENAI_MODEL` (default: gpt-4o-mini) |
| Anthropic | Claude models | `ANTHROPIC_API_KEY` (in agent provider credentials) |
| Google Gemini | Gemini models | `GOOGLE_API_KEY` (in agent provider credentials) |
| Groq | Fast inference | `GROQ_API_KEY` (in agent provider credentials) |

### Embedding Models (fastembed)
| Model | Dimensions | Use Case |
|-------|-----------|----------|
| paraphrase-multilingual-MiniLM-L12-v2-cls | 384 | Default multilingual embeddings (supports 50+ languages) |

### Communication Channels
| Service | Purpose | Config Location |
|---------|---------|-----------------|
| WhatsApp Business API | Inbound/outbound messaging | Webhook URL, HMAC secret (in agent channel config) |
| Telegram Bot API | Inbound/outbound messaging | Bot token, secret token (in agent channel config) |

### OCR & Document Processing
| Service | Purpose | Config Location |
|---------|---------|-----------------|
| Tesseract OCR | Scanned PDF text extraction | `ENABLE_OCR=true`, `OCR_LANG=eng+por` |
| pdf2image | PDF to image conversion (for OCR) | Installed via requirements.txt |

### Monitoring
| Service | Purpose | Config Location |
|---------|---------|-----------------|
| Prometheus | Metrics scraping | Scrape `GET /api/metrics` endpoint |

## Environment Configuration

### Critical Variables
| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (admin routes) | Yes | — |
| `PGHOST` | PostgreSQL host (RAG/ingestion) | Yes | `localhost` |
| `PGDATABASE` | PostgreSQL database name | Yes | `pdfkb` |
| `TENANT_ID` | Default tenant for CLI scripts | Dev only | — |
| `TENANT_TOKEN_SECRET` | JWT signing key (HS256) | Yes | — |
| `TENANT_TOKEN_ISSUER` | JWT issuer claim | Yes | `pdf-knowledge-kit` |
| `TENANT_TOKEN_AUDIENCE` | JWT audience claim | Yes | `pdf-knowledge-kit` |
| `ADMIN_API_KEY` | Admin API key for ingestion | Yes | — |
| `OPENAI_API_KEY` | OpenAI API key (optional) | No | — |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | No | `INFO` |
| `UPLOAD_MAX_SIZE` | Max upload file size (bytes) | No | `5242880` (5MB) |

See `.env.example` for full list of 40+ configuration options.

## Architectural Patterns

### 1. Repository Pattern
- **Protocol**: `AgentRepository`, `ConversationRepository`
- **Implementation**: `PostgresAgentRepository`, `PostgresConversationRepository`
- **Benefit**: Separates business logic (service layer) from data access (repository layer)

### 2. Service Layer
- **Examples**: `AgentService`, `ConversationService`, `IngestionService`
- **Benefit**: Encapsulates complex business logic, coordinates multiple repositories

### 3. Dependency Injection (FastAPI)
- **Examples**: `Depends(require_role("operator"))`, `Depends(get_db_session)`
- **Benefit**: Testable, composable route dependencies

### 4. Middleware Chain
- Order: Rate limiting → CORS → Tenant context → Logging → Routes
- **Benefit**: Cross-cutting concerns handled transparently

### 5. Strategy Pattern
- **Examples**: `ChannelAdapter` (WhatsApp, Telegram), Document parsers (PDF, DOCX)
- **Benefit**: Pluggable implementations, easy to extend

### 6. Row-Level Security (RLS)
- PostgreSQL policies automatically filter queries by `organization_id`
- Middleware sets `app.tenant_id` session variable
- **Benefit**: Defense-in-depth, prevents tenant data leakage

### 7. Context Providers (React)
- **Examples**: `AuthProvider`, `ChatProvider`
- **Benefit**: Centralized state management, avoids prop drilling

## Security Architecture

### Authentication Flow
```
1. User submits credentials → POST /api/tenant/accounts/login
2. Backend validates password (Argon2 hash comparison)
3. Generate access token (15 min expiry) + refresh token (7 days)
4. Return tokens + user data
5. Frontend stores tokens (localStorage for refresh, memory for access)
6. Auto-refresh: 5 seconds before expiry, POST /api/tenant/accounts/refresh
```

### Authorization Flow
```
1. Request arrives with Authorization: Bearer <access_token>
2. TenantContextMiddleware validates JWT signature
3. Extract claims: tenant_id, user_id, roles
4. Set app.tenant_id in PostgreSQL session
5. Route dependency checks role: require_role("operator")
6. If authorized: execute route; else: 403 Forbidden
```

### RLS Enforcement
```sql
-- Executed by middleware for every request
SET app.tenant_id = '<uuid>';

-- Example policy on chunks table
CREATE POLICY tenant_isolation ON chunks
  FOR ALL
  USING (organization_id = app.current_tenant_id());
```

## Performance Characteristics

### Vector Search
- **Typical latency**: 50-100ms for 10K chunks
- **Scaling**: HNSW index on pgvector (future optimization)
- **Pre-filtering**: RLS policies filter by tenant before vector search

### Ingestion
- **Throughput**: ~10 PDF pages/second (without OCR), ~2 pages/second (with OCR)
- **Concurrency**: ThreadPoolExecutor (default: 4 workers)
- **Bottleneck**: Embedding generation (CPU-bound)

### Chat Streaming
- **Latency**: ~200ms to first token (OpenAI API cold start)
- **Throughput**: ~50 tokens/second (OpenAI GPT-4o-mini)
- **SSE overhead**: Negligible (<10ms per event)

## Scalability Considerations

### Current Limitations
- Single-node PostgreSQL (RLS adds ~10% overhead)
- Single-node FastAPI (no horizontal scaling yet)
- In-process ThreadPoolExecutor (not distributed)

### Future Optimizations
- **Database**: Read replicas for RAG queries, connection pooling (pgbouncer)
- **API**: Horizontal scaling with load balancer (stateless design)
- **Ingestion**: Distributed task queue (Celery, RabbitMQ)
- **Vector Search**: HNSW indexing for sub-10ms queries
