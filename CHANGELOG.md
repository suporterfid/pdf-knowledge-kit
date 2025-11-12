# Changelog

All notable changes to the PDF Knowledge Kit project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Production release requirements documentation (PRODUCTION_RELEASE_REQUIREMENTS.md)
- Versioning strategy documentation (VERSION_STRATEGY.md)
- Release checklist for structured release process (RELEASE_CHECKLIST.md)
- Changelog template for tracking changes

### Changed

### Deprecated

### Removed

### Fixed

### Security

---

## [1.0.0] - TBD

### Added

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

### Security

- Environment-based secrets management
- Row-level security (RLS) preparation for multi-tenancy
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
