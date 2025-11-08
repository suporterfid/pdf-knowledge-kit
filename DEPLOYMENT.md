# Deployment Guide

This document explains how to configure, run, and ship **PDF Knowledge Kit** across development and production environments. It consolidates information from the runtime Docker assets, the environment variable template, and the automated CI workflow so teams can follow a predictable deployment process.

## 1. Prerequisites

Ensure the following tooling is installed locally or in your CI/CD runners:

- Docker Engine 24+ and Docker Compose plugin 2.20+ (required for multi-service workflows).
- Node.js 20 and npm (only necessary if you plan to build the frontend outside the Docker image).
- Python 3.12 for parity with the production image, or 3.11 to mirror CI test jobs.
- Access to required API keys (OpenAI and any custom admin keys).

Clone the repository and copy the sample environment file before starting:

```bash
cp .env.example .env
```

Update the `.env` file with values appropriate for your environment (see [Environment variables](#2-environment-variables)).

## 2. Environment variables

The application reads configuration exclusively from environment variables. The `.env.example` file captures the supported options and defaults. Update sensitive values (e.g., `OPENAI_API_KEY`) before shipping to production.【F:.env.example†L1-L57】 A quick reference is provided below.

| Category | Variable | Description |
| --- | --- | --- |
| API keys | `ADMIN_API_KEY`, `OP_API_KEY`, `VIEW_API_KEY` | Keys for privileged ingestion and operator features. Defaults are development-only and must be rotated in production. |
| Database | `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | Connection string and individual parameters used by the backend and the Postgres container. |
| Logging | `LOG_DIR`, `LOG_LEVEL`, `LOG_JSON`, `LOG_REQUEST_BODIES`, `LOG_RETENTION_DAYS`, `LOG_ROTATE_UTC` | Controls destination, format, and retention of application logs. |
| Ingestion | `DOCS_DIR`, `URLS_FILE`, `ENABLE_OCR`, `OCR_LANG` | Configure local document ingestion, URL lists, and OCR behaviour. |
| Uploads & chat | `UPLOAD_DIR`, `UPLOAD_TTL`, `UPLOAD_MAX_SIZE`, `UPLOAD_MAX_FILES`, `UPLOAD_ALLOWED_MIME_TYPES`, `CHAT_MAX_MESSAGE_LENGTH`, `SESSION_ID_MAX_LENGTH`, `ADMIN_UI_ORIGINS` | Manage upload limits and chat constraints. |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_LANG`, `SYSTEM_PROMPT` | Parameters for calling OpenAI models. |
| Branding | `BRAND_NAME`, `LOGO_URL`, `POWERED_BY_LABEL` | Customizes UI branding. |

Refer back to `.env.example` for default values and comments when in doubt.

## 3. Local development

### 3.1 Bring up the full stack with Docker Compose

The repository ships with a three-service Compose configuration: Postgres + pgvector, the FastAPI backend (with debugpy), and the Vite frontend dev server.【F:docker-compose.yml†L1-L85】

1. Copy `.env.example` to `.env` and edit values as required.
2. Launch the stack:
   ```bash
   docker compose up --build
   ```
   - `db` exposes Postgres on port 5432 with health checks to block the backend until ready.【F:docker-compose.yml†L2-L29】
   - `app` rebuilds from the `Dockerfile` and mounts the repository for live reload with debugpy listening on port 5678.【F:docker-compose.yml†L31-L64】
   - `frontend` runs `npm run dev` with polling watchers and exposes Vite on port 5173.【F:docker-compose.yml†L66-L85】
3. Access the services:
   - Backend API: http://localhost:8000
   - Frontend UI: http://localhost:5173

To rebuild after dependency changes, rerun `docker compose up --build` or rely on the `develop.watch` trigger on the backend service for Docker Desktop + Compose v2.【F:docker-compose.yml†L35-L38】

### 3.2 Running backend tests locally

With the containers running, you can exec into the backend to run tests or linting:

```bash
docker compose exec app pytest
```

Alternatively, install dependencies on the host (`pip install -r requirements.txt`) and run `pytest`. This mirrors the CI setup described in [Section 5](#5-continuous-integration--delivery).

### 3.3 Frontend development outside Docker

If you prefer to run the frontend locally without containers:

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0
```

Ensure the backend API is reachable at `http://localhost:8000` and that environment variables match your expected backend configuration.

## 4. Production deployment

### 4.1 Build the production image

The `Dockerfile` performs a multi-stage build: it compiles the frontend with Node.js 20, then copies the built static assets into a Python 3.12 slim runtime that also installs OCR dependencies and the Python requirements.【F:Dockerfile†L1-L29】 To produce the image:

```bash
docker build -t your-registry/pdf-knowledge-kit:latest .
```

Push to your registry once satisfied:

```bash
docker push your-registry/pdf-knowledge-kit:latest
```

### 4.2 Run the container

At runtime the image exposes port 8000 and expects the same environment variables defined in `.env`.【F:Dockerfile†L9-L29】 For single-container deployments:

```bash
docker run -d \
  --name pdf-knowledge-kit \
  -p 8000:8000 \
  --env-file /path/to/production.env \
  -v /var/log/pdf-knowledge-kit:/var/log/app \
  your-registry/pdf-knowledge-kit:latest
```

Provision a managed Postgres instance with pgvector extensions enabled and point `DATABASE_URL`/`PG*` variables to that service. Mount any directories needed for persistent uploads or logs.

### 4.3 Database migrations

If you maintain schema migrations (see `migrations/`), execute them against the production database before first boot or as part of your release pipeline. For example:

```bash
docker compose run --rm app alembic upgrade head
```

Adjust the command to your orchestration tooling as needed.

### 4.4 Observability considerations

The container prepares `/var/log/app` with appropriate permissions, so mounting a volume or centralized logging agent to that path will collect structured logs. Toggle `LOG_JSON` in production to emit JSON-formatted logs for ingestion by log processors.【F:Dockerfile†L20-L29】【F:.env.example†L20-L26】

## 5. Continuous integration & delivery

GitHub Actions provides multiple workflows for CI/CD:

### Testing and Quality Assurance
- **`.github/workflows/tests.yml`**: Runs on each push to `main` and pull requests. Executes Python tests with `pytest` and frontend tests with Vitest.
- **`.github/workflows/lint.yml`**: Code quality checks including Python linting (Ruff, Black), type checking (MyPy), security scanning (Bandit), and dependency audits.
- **`.github/workflows/security.yml`**: Security scanning with CodeQL, secret detection (TruffleHog), dependency review, and container scanning (Trivy). Runs on push, pull requests, and weekly schedules.

### Release Automation
- **`.github/workflows/release.yml`**: Automated release workflow triggered by version tags (e.g., `v1.0.0`). Builds multi-platform Docker images, publishes to GitHub Container Registry, and creates GitHub Releases with automated changelog extraction.

### Release Process
For detailed information on creating releases, see:
- **[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)**: Step-by-step release process
- **[VERSION_STRATEGY.md](VERSION_STRATEGY.md)**: Semantic versioning guidelines
- **[PRODUCTION_RELEASE_REQUIREMENTS.md](PRODUCTION_RELEASE_REQUIREMENTS.md)**: Comprehensive production readiness requirements

To create a release:
1. Follow the [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
2. Use `tools/bump_version.py` to update version numbers
3. Update [CHANGELOG.md](CHANGELOG.md) with release notes
4. Create and push a Git tag (e.g., `git tag -a v1.0.0 -m "Release v1.0.0" && git push origin v1.0.0`)
5. The release workflow automatically builds images and creates the GitHub Release

## 6. Troubleshooting

- **Database connection errors**: Confirm the `db` service is healthy and credentials in `.env` match the defaults; pgvector exposes port 5432 locally.【F:docker-compose.yml†L2-L24】
- **Missing OCR languages**: Mount additional `tessdata` files into `/usr/share/tesseract-ocr/tessdata` if you require more languages; a commented volume example is present in the Compose file.【F:docker-compose.yml†L55-L58】
- **Frontend cannot reach backend**: Ensure ports 5173 (frontend) and 8000 (backend) are published, and update `VITE_*` variables if you customize hostnames.

With these steps, teams can reproducibly configure, test, and deploy PDF Knowledge Kit across local and production environments.
