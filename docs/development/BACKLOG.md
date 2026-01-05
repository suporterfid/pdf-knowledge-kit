# Development Backlog
> Last updated: 2025-12-31

## Legend
- Effort: `[S]` <2h | `[M]` 2-8h | `[L]` 1-3d | `[XL]` >3d
- Priority: 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

## Critical 🔴

- [ ] `[M]` Add webhook signature verification tests — *Identified in security assessment, prevent unauthorized webhook calls*
- [ ] `[S]` Update outdated Python dependencies (cryptography 41→46) — *Security patches, see docs/development/TECHNICAL_DEBT.md*
- [ ] `[M]` Implement SSE error recovery edge case handling — *Frontend sometimes fails to reconnect after network drop, see frontend/src/chat.tsx:150*
- [ ] `[S]` Add CSRF protection for state-changing endpoints — *Missing for POST /api/feedback, /api/chat endpoints*

## High Priority 🟠

- [ ] `[L]` Expand test coverage for connectors (SQL, REST, transcription) — *Currently minimal coverage, target 60%+, see tests/test_*_connector.py*
- [ ] `[M]` Add bulk document import API endpoint — *Requested feature, would significantly improve UX for large migrations*
- [ ] `[M]` Implement job cancellation UI in admin panel — *Backend supports cancellation (app/ingestion/service.py:456), but no UI*
- [ ] `[M]` Add conversation export functionality — *Export conversations to JSON/CSV for analysis, requested by users*
- [ ] `[M]` Improve error messages in AuthProvider — *Generic "Login failed" doesn't help debug, see frontend/src/auth/AuthProvider.tsx:234*
- [ ] `[L]` Create connector developer guide documentation — *Enable third-party connector development, see docs/development/ROADMAP.md Phase 2*
- [ ] `[S]` Add rate limit headers to API responses — *Return X-RateLimit-Remaining, X-RateLimit-Reset for better client handling*
- [ ] `[M]` Implement pgbouncer for connection pooling — *Prepare for horizontal scaling, reduce connection overhead*

## Medium Priority 🟡

- [ ] `[M]` Add HNSW indexing to pgvector for faster queries — *Current IVFFlat is sufficient for <100K chunks, HNSW needed for 1M+*
- [ ] `[L]` Create analytics dashboard with query metrics — *Track query frequency, latency, failure rates, feedback scores*
- [ ] `[M]` Add Google Drive connector — *Requested by 3+ users, see docs/development/ROADMAP.md Phase 2*
- [ ] `[M]` Implement conversation search functionality — *Search across conversation history by content, participant, date*
- [ ] `[S]` Add Docker healthcheck for frontend service — *Currently only backend has healthcheck, see docker-compose.yml:35*
- [ ] `[M]` Create performance benchmarking suite — *Baseline performance metrics for regression testing*
- [ ] `[S]` Add logging for failed embedding generation — *Silent failures make debugging difficult, see app/ingestion/service.py:789*
- [ ] `[M]` Implement tenant usage quotas — *Track document count, chunk count, API calls per tenant*
- [ ] `[S]` Add support for custom chunk size/overlap per source — *Currently hardcoded 500/50, see app/ingestion/chunking.py:12*
- [ ] `[M]` Create admin UI for agent version management — *Backend supports versioning (app/agents/service.py:220), needs UI*
- [ ] `[L]` Add multi-language support for frontend — *i18n infrastructure, starting with Portuguese and English*
- [ ] `[M]` Implement document deduplication logic — *Prevent duplicate chunks when same document ingested twice*

## Low Priority 🟢

- [ ] `[S]` Add dark mode toggle to admin panel — *Frontend chat has dark mode, admin panel doesn't*
- [ ] `[M]` Create Kubernetes deployment manifests — *For enterprise deployments, see docs/development/ROADMAP.md Phase 4*
- [ ] `[S]` Add RSS feed connector — *Monitor blogs, news sites for ingestion*
- [ ] `[M]` Implement agent testing UI with synthetic data — *Backend has test_agent API (app/agents/service.py:310), needs UI*
- [ ] `[S]` Add support for .txt file ingestion — *Simple parser, low effort*
- [ ] `[L]` Create mobile-responsive admin dashboard — *Currently desktop-only, needs responsive design*
- [ ] `[M]` Add support for custom system prompts per agent — *Currently uses global SYSTEM_PROMPT, see app/main.py:410*
- [ ] `[S]` Implement log level switching without restart — *Dynamic log level via API endpoint*
- [ ] `[M]` Add support for CSV export of feedback data — *Export feedback for analysis, see app/routers/feedback_api.py*
- [ ] `[L]` Create agent marketplace (community agents) — *Long-term vision, see docs/development/ROADMAP.md Future*
- [ ] `[S]` Add support for .docm (Word macro) files — *Edge case, low priority*
- [ ] `[M]` Implement conversation tagging system — *Tag conversations for categorization, filtering*

## Tech Debt / Refactoring

- [ ] `[M]` Refactor app/ingestion/service.py (1,238 lines) — *Split into smaller modules by responsibility, see docs/development/TECHNICAL_DEBT.md*
- [ ] `[S]` Replace legacy ingest.py CLI with typer — *Current argparse implementation is verbose, see ingest.py:1-120*
- [ ] `[M]` Migrate frontend from CRA patterns to Vite best practices — *Some legacy patterns remain from CRA migration*
- [ ] `[S]` Remove dead code in app/nlp.py — *Unused entity extraction functions, see app/nlp.py:85-105*
- [ ] `[M]` Standardize error response format across all routers — *Some return plain text, some JSON, see app/routers/**
- [ ] `[S]` Add type hints to all public functions — *~15% of functions lack type hints, breaks mypy strict mode*
- [ ] `[M]` Refactor AuthProvider to use reducer pattern — *Complex state updates, see frontend/src/auth/AuthProvider.tsx:1-578*
- [ ] `[S]` Remove console.log statements from production build — *Several debug logs remain, see frontend/src/components/**

## Documentation

- [ ] `[M]` Expand API_REFERENCE.md with request/response examples — *Current docs lack examples for complex endpoints*
- [ ] `[S]` Document RLS policies in ARCHITECTURE.md — *Explain how tenant isolation works at DB level*
- [ ] `[M]` Create deployment runbook for AWS — *Step-by-step guide for ECS/RDS deployment*
- [ ] `[S]` Add architecture diagrams (data flow, system context) — *Visual documentation for onboarding*
- [ ] `[M]` Document environment variable validation — *Which vars are required vs optional, validation rules*
- [ ] `[S]` Create troubleshooting guide for common issues — *OCR failures, connection errors, token expiry*
- [ ] `[L]` Write connector developer tutorial — *End-to-end guide for building custom connector*
- [ ] `[S]` Document backup and restore procedures — *PostgreSQL backup strategy, disaster recovery*

## Testing

- [ ] `[M]` Add integration tests for WhatsApp webhook flow — *End-to-end test with signature verification*
- [ ] `[M]` Add integration tests for Telegram webhook flow — *End-to-end test with secret token*
- [ ] `[S]` Add unit tests for app/nlp.py entity extraction — *Currently no test coverage*
- [ ] `[M]` Create E2E tests for admin dashboard workflows — *Playwright tests for job monitoring, source management*
- [ ] `[S]` Add tests for OCR failure scenarios — *Tesseract not installed, invalid image format*
- [ ] `[M]` Add load tests with Locust — *Simulate 1K concurrent users, identify bottlenecks*
- [ ] `[S]` Add tests for JWT expiry edge cases — *Token expires during request, refresh token invalid*
- [ ] `[M]` Create test fixtures for multi-tenant scenarios — *Simplify tenant isolation tests*

## Infrastructure

- [ ] `[M]` Set up GitHub Actions CI/CD pipeline — *Automated testing, linting, deployment*
- [ ] `[S]` Add pre-commit hooks (black, ruff, mypy) — *Enforce code quality before commit*
- [ ] `[M]` Set up Sentry for error tracking — *Centralized error monitoring and alerting*
- [ ] `[S]` Configure renovate for dependency updates — *Automated PR for dependency bumps*
- [ ] `[M]` Set up Prometheus + Grafana for monitoring — *Visualize metrics from /api/metrics endpoint*
- [ ] `[L]` Create staging environment for testing — *Separate environment for pre-production validation*
- [ ] `[M]` Implement blue-green deployment strategy — *Zero-downtime deployments*

## Completed ✅

- [x] `[L]` Implement chat history persistence — *completed 2025-01-XX, PR #256*
- [x] `[M]` Fix Docker login errors (psycopg2 vs psycopg3) — *completed 2025-XX-XX, see CHANGELOG.md*
- [x] `[M]` Normalize authentication routes — *completed 2025-XX-XX, /api/tenant/accounts/*
- [x] `[S]` Add AuthProvider rate limiting — *completed 2025-XX-XX, max 3 attempts, 5s throttle*
- [x] `[L]` Implement Row-Level Security (RLS) — *completed 2024-XX-XX, see schema.sql*
- [x] `[L]` Build agent orchestration system — *completed 2024-XX-XX, app/agents/*
- [x] `[M]` Add multi-tenant authentication — *completed 2024-XX-XX, JWT with tenant claims*
- [x] `[XL]` Implement multi-channel conversation management — *completed 2024-XX-XX, WhatsApp + Telegram*
