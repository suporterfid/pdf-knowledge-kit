# Changelog

All notable changes to the PDF Knowledge Kit project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Summary

- Correções críticas de login Docker: psycopg2 e conexão frontend-backend
- Correções críticas para browser freeze no ambiente de desenvolvimento (DryRun-Dev-2025118)
- Todas as 4 issues identificadas foram resolvidas em ~50 minutos (89% mais rápido que estimado)

### Added

- Rate limiting e proteção contra infinite loops no AuthProvider (ISSUE-003)
  - Timeout de 10 segundos para requisições de refresh
  - Mínimo de 5 segundos entre tentativas de refresh
  - Máximo de 3 tentativas consecutivas
  - Reset automático de contador em login/registro manual
- Variáveis de ambiente TENANT_TOKEN_* no .env.example (ISSUE-004)
  - TENANT_TOKEN_SECRET com exemplo de valor de desenvolvimento
  - TENANT_TOKEN_ISSUER com valor padrão
  - TENANT_TOKEN_AUDIENCE com valor padrão
  - Documentação e instruções para geração de secrets seguros

### Changed

- ConfigProvider agora usa fetch nativo ao invés de useAuthenticatedFetch (ISSUE-002)
  - Remove dependência circular com AuthProvider
  - Melhora performance de carregamento inicial
  - Adiciona tratamento de erro com console.warn

### Fixed

- **[CRÍTICO]** Erro de login Docker: ModuleNotFoundError psycopg2
  - SQLAlchemy estava tentando usar psycopg2 mas requirements.txt tem psycopg3
  - Solução: app/models/session.py agora converte postgresql:// para postgresql+psycopg://
  - Mantém compatibilidade com sqlite:// e postgresql+psycopg:// URLs existentes
- **[CRÍTICO]** Erro de login Docker: Frontend ECONNREFUSED ao conectar no backend
  - Frontend iniciava antes do backend estar pronto para aceitar conexões
  - Solução: Adicionado healthcheck ao serviço API e frontend aguarda API saudável
  - Healthcheck usa endpoint existente /api/health com start_period de 40s
- **[CRÍTICO]** Incompatibilidade de rotas de autenticação (ISSUE-001)
  - `/api/auth/refresh` → `/api/tenant/accounts/refresh`
  - `/api/auth/login` → `/api/tenant/accounts/login`
  - `/api/auth/register` → `/api/tenant/accounts/register`
  - `/api/auth/logout` → `/api/tenant/accounts/logout`
- **[CRÍTICO]** Race condition no ConfigProvider causando chamadas API prematuras (ISSUE-002)
- **[ALTO]** AuthProvider criando loops infinitos de refresh sem proteção (ISSUE-003)
- **[MÉDIO]** Configurações de tenant token ausentes dificultando setup inicial (ISSUE-004)

### Deprecated

### Removed

### Security

- Implementadas proteções contra ataques de DoS via infinite loops no refresh de autenticação
- Adicionado timeout para prevenir requests pendentes indefinidamente

---

## [1.0.0] - 2025-11-15

### Summary

- Primeira versão estável reunindo backend FastAPI, frontend React e trilha operacional completas com multi-inquilinos protegidos por RLS.
- Branch `release/v1.0.0` aprovada pelo comitê de plataforma e fechada após execução bem-sucedida do workflow [Release](.github/workflows/release.yml) para o tag anotado `v1.0.0`.
- Artefatos publicados: [GitHub Release v1.0.0][1.0.0] e imagem [`ghcr.io/chatvolt/pdf-knowledge-kit:v1.0.0`][1.0.0-ghcr] disponível no registry corporativo.

### Added

- Production release requirements documentation (PRODUCTION_RELEASE_REQUIREMENTS.md)
- Versioning strategy documentation (VERSION_STRATEGY.md)
- Release checklist for structured release process (RELEASE_CHECKLIST.md)
- Changelog template for tracking changes
- Row Level Security (RLS) implementation for multi-tenancy (migration 011)
- Test suite for RLS tenant isolation (`test_rls_tenant_isolation.py`)
- Complete FastAPI backend with semantic search capabilities
- React/TypeScript frontend with ChatGPT-inspired interface
- PostgreSQL + pgvector integration for vector similarity search
- Document ingestion from PDFs, Markdown, and URLs
- Multi-connector support:
  - Local file system ingestion
  - URL/web page ingestion
  - Database connector (SQL queries)
  - REST API connector
  - Transcription connector (mock, Whisper, AWS Transcribe)
- Streaming chat interface with Server-Sent Events (SSE)
- OpenAI integration for LLM-powered responses
- Multi-language embedding support (50+ languages via paraphrase-multilingual model)
- OCR support with tesseract for scanned documents
- RBAC with three roles (admin, operator, viewer)
- API key authentication
- Rate limiting with SlowAPI
- Prometheus metrics at `/api/metrics`
- Comprehensive logging with daily rotation
- Conversation history management
- File upload support with temporary storage
- Docker Compose orchestration
- Database migrations with Alembic
- Comprehensive test suite (44 tests)
- Frontend tests with Vitest
- API reference documentation
- Deployment guide
- Operator guide for day-2 operations
- Architecture documentation
- Frontend development guide
- GitHub Actions CI for automated testing
- Dependabot for devcontainer updates

### Changed

- Hardened database update helpers to compose SQL queries using `psycopg.sql`
  for agent, conversation, and source repositories, eliminating potential SQL
  injection vectors flagged by security tooling.
- Replaced direct `print` usage in administrative CLI scripts with consistent
  stdout helpers to satisfy linting and security requirements.
- Introduced structured dependency aliases in authentication and ingestion
  routers to align with Ruff's dependency-injection guidance and improve type
  clarity.

### Fixed

- Added defensive logging around optional third-party integrations and file
  parsing fallbacks to make ingestion error handling observable without failing
  silently.
- Documents and chunks tables now include `organization_id` column for tenant isolation.
- Ingestion storage layer updated to set `organization_id` from tenant context.
- RAG query enhanced with inline documentation explaining the RLS behavior.

### Security

- Environment-based secrets management
- Row-level security (RLS) enforcement for multi-tenancy, with PostgreSQL policies filtering by the `app.tenant_id` session variable and backward compatibility when unset
- Input validation and sanitization
- CORS configuration
- Rate limiting to prevent abuse
- Secure file upload handling

---

## Release Types

- **[Unreleased]** - Changes in development that haven't been released yet
- **[X.Y.Z]** - Released versions with date
- **[X.Y.Z-alpha.N]** - Alpha pre-releases (early development)
- **[X.Y.Z-beta.N]** - Beta pre-releases (feature complete, may have bugs)
- **[X.Y.Z-rc.N]** - Release candidates (ready for production testing)

## Change Categories

- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Features that will be removed in future releases
- **Removed** - Features that have been removed
- **Fixed** - Bug fixes
- **Security** - Security improvements and vulnerability fixes

## Guidelines for Maintaining This Changelog

1. **Update for Every Release:** Add a new section for each version
2. **Group Changes:** Use the standard categories (Added, Changed, etc.)
3. **Be Specific:** Describe what changed and why
4. **Reference Issues:** Link to GitHub issues/PRs when applicable
5. **Date Releases:** Include release dates in YYYY-MM-DD format
6. **Keep Unreleased Section:** Always maintain an [Unreleased] section for upcoming changes

## Example Entry Format

```markdown
## [1.2.0] - 2025-03-15

### Added

- New SharePoint connector for document ingestion (#123)
- Support for XLSX file format (#124)
- Configurable chunk size for document splitting (#125)

### Changed

- Improved query performance by 40% through index optimization (#126)
- Updated OpenAI SDK to v2.0 (#127)

### Fixed

- Fixed memory leak in long-running chat sessions (#128)
- Corrected PDF parsing for documents with special characters (#129)

### Security

- Updated dependencies to address CVE-2025-1234 (#130)
- Added CSRF protection to admin endpoints (#131)
```

---

**Maintained by:** PDF Knowledge Kit Development Team
**First version:** 2025-11-08

[Unreleased]: https://github.com/chatvolt/pdf-knowledge-kit/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/chatvolt/pdf-knowledge-kit/releases/tag/v1.0.0
[1.0.0-ghcr]: https://github.com/orgs/chatvolt/packages/container/package/pdf-knowledge-kit/versions?filters%5Bversion_name%5D=v1.0.0
