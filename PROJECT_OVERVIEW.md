# Project Overview

## 1. Repository Overview

### Purpose and Architecture

- Build a knowledge base from PDFs and Markdown with semantic search capabilities using FastAPI backend and React frontend.
- Text is chunked, embedded with multilingual model, and stored in PostgreSQL with pgvector for k‑NN search.
- Chat endpoints can answer questions and stream responses, optionally leveraging OpenAI models.

### Technologies

- **Backend:** Python 3.11+, FastAPI, pgvector, fastembed, OpenAI SDK.
- **Frontend:** React + TypeScript com Vite e Vitest.
- **Database:** PostgreSQL 16 com extensão pgvector.
- **Connectors:** drivers SQL (`psycopg`), REST (`requests`), e SDKs de transcrição opcionais (`boto3`, `faster-whisper`, `openai-whisper`).

### Directory Structure

| Path                               | Responsibility                                                                                                               |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `app/`                             | FastAPI application with ingestion service, routers, security utilities, SSE helpers, static assets.                         |
| `app/ingestion/`                   | Document ingestion, chunking, embedding (`EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"`). |
| `app/routers/`                     | REST endpoints including admin ingestion and authentication.                                                                 |
| `frontend/`                        | React/TypeScript client with chat interface and admin UI.                                                                    |
| `migrations/`                      | Database migration scripts.                                                                                                  |
| `tests/`                           | Python and frontend tests covering ingestion, chat, admin APIs and more.                                                     |
| `tools/`                           | Utility scripts.                                                                                                             |
| `Dockerfile`, `docker-compose.yml` | Container build and orchestration.                                                                                           |

## 2. Deployment Options

### Local Development

Prerequisites:

- Docker & Docker Compose
- Python 3.10+
- (Optional for OCR) `tesseract-ocr` and related language packs

Steps:

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `docker compose up -d db`
4. `pytest`
5. `uvicorn app.main:app --reload`
6. For the frontend: `cd frontend && npm install && npm run dev`

### Environment Configuration

Key environment variables (see `.env.example`):

| Variable                                                                       | Description                                                     |
| ------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| `TENANT_TOKEN_SECRET`, `TENANT_TOKEN_ISSUER`, `TENANT_TOKEN_AUDIENCE`          | Parâmetros para assinar e validar JWTs de acesso multi-tenant.  |
| `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS`                        | (Opcional) ajustar tempo de expiração dos tokens emitidos.      |
| `DATABASE_URL` / `PG*`                                                         | PostgreSQL connection details.                                  |
| `LOG_DIR`, `LOG_LEVEL`, `LOG_JSON`                                             | Logging configuration.                                          |
| `DOCS_DIR`, `ENABLE_OCR`, `OCR_LANG`                                           | Ingestion and OCR behaviour.                                    |
| `UPLOAD_DIR`, `UPLOAD_MAX_SIZE`, `UPLOAD_MAX_FILES`, `CHAT_MAX_MESSAGE_LENGTH` | Upload and chat limits.                                         |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_LANG`                                | Optional LLM integration.                                       |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`                     | Needed when the transcription connector targets AWS Transcribe. |
| `ADMIN_UI_ORIGINS`                                                             | Enable CORS for an external admin UI host.                      |

### Docker Deployment

`docker-compose.yml` defines services:

- **db:** pgvector/postgresql with health checks and persisted volume.
- **api:** builds the backend image, mounts `docs/` and `logs/`, exposes port `8000`.

### Reverse Proxy

A sample `Caddyfile` proxies requests from `example.com` to the backend service.

### Scalability & Extensions

- Swap pgvector for other vector databases (e.g., Qdrant, Weaviate) by adapting ingestion/storage modules.
- Deploy multiple backend instances behind a load balancer; stateless API enables horizontal scaling.
- Frontend is static and can be served by any CDN.
- Add new connectors by following the patterns in `app/ingestion/connectors/` and extending the catalog documented in `README.md`.

## 3. CI/CD Guidance

### GitHub Actions

Existing workflow `tests.yml` runs on pushes and pull requests:

- Installs Python dependencies and executes `pytest`.
- Installs Node dependencies and runs frontend tests (`npm test`).

### Suggested Automations

- Linting with `ruff` or `flake8`, TypeScript `tsc` check.
- Build and publish Docker images.
- Security scanning (e.g., `pip-audit`, `npm audit`).
- Deployment steps to push containers to a registry or deploy to cloud platforms.

### Best Practices

- Use caching for Python and Node packages to speed up builds.
- Run tests in parallel matrix for multiple Python/Node versions if needed.
- Require status checks before merges; protect `main` branch.
- Keep workflows modular (separate lint, test, build jobs) for clarity.

## 4. AI Agent Enablement

### API Overview

- `GET /api/health` – health probe.
- `GET /api/config` – returns branding and upload limits.
- `POST /api/upload` – temporary file storage for chat attachments.
- `POST /api/ask` – returns answer and source chunks.
- `POST /api/chat` & `GET /api/chat` – streaming chat responses with optional file attachments.
- `Router /api/tenant/accounts` – gerencia organizações, login/logout, convites e rotação de tokens de acesso.
- `Router /api/admin/ingest` – start ingestion jobs (`/local`, `/url`, `/urls`, `/database`, `/api`, `/transcription`), manage connector definitions, inspect job metadata and logs.

#### Connector endpoints

| Endpoint                                       | Description                                                             | Sample payload highlights                                                                            |
| ---------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `POST /api/admin/ingest/database`              | Run SQL queries and ingest result sets.                                 | `params.queries` with `sql`, `text_column`, `id_column`; optional `credentials.values` for DB login. |
| `POST /api/admin/ingest/api`                   | Crawl REST APIs and ingest JSON responses.                              | `params` accepts pagination hints, `text_fields`, optional headers/token credentials.                |
| `POST /api/admin/ingest/transcription`         | Download/transcribe media files.                                        | `params.provider` (`mock`, `whisper`, `aws_transcribe`), optional caching and metadata fields.       |
| `POST /api/admin/ingest/connector_definitions` | Persist reusable connector templates.                                   | Store `type`, `params`, and `credentials` for future jobs.                                           |
| `GET /api/admin/ingest/jobs/{id}`              | Retrieve job status, `job_metadata`, `sync_state`, and version history. | Combine with `/logs?offset=` to stream log tails.                                                    |

### Configuration & Data Flow

1. Docs and URLs ingested via CLI (`ingest.py`) or admin API.
2. Text chunked and embedded using multilingual model.
3. Chunks stored in PostgreSQL with pgvector; `query.py` performs semantic queries.
4. Chat endpoints assemble context and stream responses; OpenAI model used when available.

### Testing

- `tests/` includes unit and integration tests (44 passing, 5 skipped) covering ingestion, chat, admin endpoints, logging and more.
- Frontend tests use Vitest and Testing Library.
- Connector suites rely on [`testing.postgresql`](https://pypi.org/project/testing.postgresql/) for ephemeral databases and mock transcription providers; install optional SDKs (`boto3`, `faster-whisper`, `openai-whisper`) to exercise real providers locally.
- See `README.md` and `tools/register_connector.py` for end-to-end admin flows that mimic CI scenarios.

### Guidance for Agents

- Inspect `app/` modules to extend APIs or improve ingestion accuracy.
- Use `tests/` as templates when adding features; keep coverage high.
- Propose enhancements (e.g., new embeddings, additional storage backends, richer admin UI) with accompanying tests.

## 5. References

- CLI utilities: `ingest.py`, `query.py`.
- Database schema: `schema.sql`, migration scripts in `migrations/`.
- Operations playbook: `OPERATOR_GUIDE.md`.
