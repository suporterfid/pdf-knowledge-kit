# Technical Debt Registry
> Last updated: 2025-12-31

## Critical

### Outdated Security Dependencies
- **Location**: `requirements.txt`
- **Impact**: Potential security vulnerabilities in cryptography (41.0.7 → 46.0.3)
- **Remediation**: Run `pip install --upgrade cryptography` and test thoroughly. Check for breaking changes in release notes.
- **Effort**: `[S]` <2h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Update outdated Python dependencies

### Missing CSRF Protection
- **Location**: `app/main.py`, `app/routers/feedback_api.py`
- **Impact**: State-changing endpoints (/api/feedback, /api/chat) vulnerable to CSRF attacks
- **Remediation**: Implement double-submit cookie pattern or SameSite cookie attribute. Add CSRF token validation middleware.
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Add CSRF protection

### Webhook Signature Verification Gaps
- **Location**: `app/routers/webhooks.py:87-120`
- **Impact**: Missing tests for edge cases (invalid signatures, replay attacks, timing attacks)
- **Remediation**: Add comprehensive test suite covering:
  - Invalid HMAC signatures
  - Expired timestamps (prevent replay attacks)
  - Timing attack resistance (constant-time comparison)
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Add webhook signature verification tests

## High

### Oversized Service Module
- **Location**: `app/ingestion/service.py` (1,238 lines)
- **Impact**: Difficult to navigate, test, and maintain. High cyclomatic complexity.
- **Remediation**: Split into smaller modules:
  - `service.py` — High-level orchestration only (~300 lines)
  - `job_manager.py` — Job lifecycle management
  - `schema_manager.py` — Database schema operations
  - `batch_processor.py` — Batch ingestion logic
- **Effort**: `[L]` 1-3d
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Refactor app/ingestion/service.py

### Oversized AuthProvider Component
- **Location**: `frontend/src/auth/AuthProvider.tsx` (578 lines)
- **Impact**: Complex state management, difficult to test, prone to bugs
- **Remediation**: Refactor to use reducer pattern:
  - Extract auth logic into `useAuthReducer` hook
  - Separate token refresh logic into `useTokenRefresh` hook
  - Split into smaller components (LoginForm, RegisterForm, etc.)
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Refactor AuthProvider

### Inconsistent Error Response Format
- **Location**: `app/routers/*.py` (all routers)
- **Impact**: API clients can't handle errors uniformly. Some return plain text, some JSON.
- **Remediation**: Define standard error schema:
  ```json
  {
    "error": {
      "code": "INVALID_INPUT",
      "message": "Email is required",
      "details": {"field": "email"}
    }
  }
  ```
  Implement custom exception handler in `app/main.py`.
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Standardize error response format

### SSE Error Recovery Edge Cases
- **Location**: `frontend/src/chat.tsx:150-200`
- **Impact**: Frontend sometimes fails to reconnect after network interruption or server restart
- **Remediation**:
  - Add exponential backoff with jitter
  - Implement connection state machine (CONNECTING, CONNECTED, DISCONNECTED, ERROR)
  - Add event source ready state monitoring
  - Test with network throttling and server restarts
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Implement SSE error recovery

### No Connection Pooling
- **Location**: `app/models/session.py`, database connections
- **Impact**: Each request creates new DB connection. High latency, potential connection exhaustion under load.
- **Remediation**: Implement pgbouncer for connection pooling:
  - Set up pgbouncer container in docker-compose.yml
  - Configure transaction pooling mode
  - Update DATABASE_URL to point to pgbouncer
  - Document configuration in DEPLOYMENT.md
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Implement pgbouncer

## Medium

### Legacy CLI Implementation
- **Location**: `ingest.py`, `query.py` (argparse-based)
- **Impact**: Verbose code, poor user experience, difficult to extend
- **Remediation**: Migrate to typer for better UX:
  - Rich help text with colors
  - Auto-completion support
  - Type-safe arguments
  - Subcommands for different operations
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Replace legacy CLI with typer

### Dead Code in NLP Module
- **Location**: `app/nlp.py:85-105`
- **Impact**: Unused entity extraction functions add maintenance burden and confusion
- **Remediation**: Remove unused functions:
  - `extract_phone_numbers()` — Never called
  - `extract_account_numbers()` — Never called
  - Or move to separate utils module if intended for future use
- **Effort**: `[S]` <2h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Remove dead code in app/nlp.py

### Missing Type Hints
- **Location**: Multiple files (15% of functions)
- **Impact**: Breaks mypy strict mode, reduces IDE autocomplete quality, increases bug risk
- **Remediation**: Add type hints to all public functions:
  - Start with `app/ingestion/parsers/*.py` (highest impact)
  - Use `mypy --strict` to identify missing hints
  - Add `# type: ignore` with comments for unavoidable cases
- **Effort**: `[M]` 2-8h (can be done incrementally)
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Add type hints

### Hardcoded Chunking Parameters
- **Location**: `app/ingestion/chunking.py:12-25`
- **Impact**: Chunk size (500) and overlap (50) are hardcoded. Not optimal for all document types.
- **Remediation**:
  - Add `chunk_size` and `chunk_overlap` fields to `sources` table
  - Allow per-source configuration via API
  - Provide sensible defaults based on document type (PDF: 500, code: 1000, etc.)
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Custom chunk size/overlap per source

### No Document Deduplication
- **Location**: `app/ingestion/storage.py`
- **Impact**: Same document can be ingested multiple times, wasting storage and degrading search quality
- **Remediation**:
  - Compute content hash (SHA256) during ingestion
  - Check for existing document with same hash before creating new one
  - Optionally update metadata and re-embed if content unchanged
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Implement document deduplication

### No Tenant Usage Quotas
- **Location**: Multi-tenant system (no quota enforcement)
- **Impact**: Single tenant can consume excessive resources (storage, API calls), impacting others
- **Remediation**:
  - Add `quotas` table (tenant_id, document_limit, chunk_limit, api_call_limit)
  - Enforce limits in ingestion and query endpoints
  - Return 429 Too Many Requests with Retry-After header
  - Add quota management UI in admin panel
- **Effort**: `[L]` 1-3d
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Implement tenant usage quotas

### Production Debug Logs
- **Location**: `frontend/src/components/*.tsx`
- **Impact**: Console.log statements leak internal state to browser console, potential security risk
- **Remediation**:
  - Remove all `console.log` statements
  - Use conditional logging: `if (import.meta.env.DEV) console.log(...)`
  - Configure Vite to strip console statements in production builds
- **Effort**: `[S]` <2h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Remove console.log from production

## Low (Accepted)

### CRA Legacy Patterns in Frontend
- **Location**: `frontend/src/*` (some components)
- **Impact**: Minor - some patterns from Create React App migration remain, but don't cause issues
- **Remediation**: Gradually migrate to Vite best practices during feature work. Not urgent.
- **Effort**: `[M]` 2-8h
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Migrate frontend patterns
- **Note**: Accepted for now, will address opportunistically

### No HNSW Indexing
- **Location**: `schema.sql` (pgvector uses IVFFlat by default)
- **Impact**: Vector search latency scales linearly with corpus size. Acceptable for <100K chunks, problematic for 1M+.
- **Remediation**: Add HNSW index when pgvector HNSW is production-ready:
  ```sql
  CREATE INDEX chunks_embedding_hnsw_idx ON chunks
  USING hnsw (embedding vector_l2_ops);
  ```
- **Effort**: `[M]` 2-8h (+ testing)
- **Linked Task**: [BACKLOG.md](BACKLOG.md) — Add HNSW indexing
- **Note**: Accepted - current performance is sufficient for target scale (<100K chunks)

### Legacy Migration Code
- **Location**: `app/migrations/011_add_auth_tables.py:34`, `app/migrations/012_add_tenant_ids.py:86`
- **Impact**: Migration scripts contain fallback logic for older databases, adding complexity
- **Remediation**: Remove legacy migration logic after all deployments upgraded to v1.0+
- **Effort**: `[S]` <2h
- **Linked Task**: None (deferred to v2.0)
- **Note**: Accepted - needed for backward compatibility during v1.x

### Single-Node Architecture
- **Location**: Entire system (no horizontal scaling)
- **Impact**: Limited to single-node capacity (~10K concurrent users estimated)
- **Remediation**: See [ROADMAP.md](ROADMAP.md) Phase 4 - Horizontal scaling architecture
- **Effort**: `[XL]` weeks
- **Linked Task**: [ROADMAP.md](ROADMAP.md#phase-4-scale--performance-q4-2025)
- **Note**: Accepted - sufficient for current scale, roadmap item for Q4 2025

### No Multi-Region Support
- **Location**: Deployment architecture
- **Impact**: High latency for users far from primary region, no disaster recovery
- **Remediation**: See [ROADMAP.md](ROADMAP.md) Phase 4 - Multi-region deployment
- **Effort**: `[XL]` weeks
- **Linked Task**: [ROADMAP.md](ROADMAP.md#phase-4-scale--performance-q4-2025)
- **Note**: Accepted - not needed for current deployment scale

## Monitoring & Metrics

### Track Technical Debt Over Time
- [ ] Set up CodeClimate or SonarQube for automated debt tracking
- [ ] Define debt reduction goals (e.g., reduce critical/high items by 50% in Q1 2025)
- [ ] Include debt metrics in quarterly reviews

### Debt Prevention
- [ ] Add linting rules to prevent new hardcoded values
- [ ] Require type hints for all new functions (mypy strict mode)
- [ ] Enforce max file size (500 lines) in CI/CD
- [ ] Require tests for all new features (coverage threshold: 60%)

## Prioritization Framework

### Decision Matrix
| Debt Item | Impact | Effort | Priority |
|-----------|--------|--------|----------|
| High impact, low effort | High | Low | 🔴 Critical |
| High impact, high effort | High | High | 🟠 High |
| Low impact, low effort | Low | Low | 🟡 Medium |
| Low impact, high effort | Low | High | 🟢 Low |

### Allocation Strategy
- Allocate 20% of each sprint to tech debt reduction
- Critical items: Address immediately (block releases if needed)
- High items: Schedule within 2 sprints
- Medium items: Opportunistic (during related feature work)
- Low items: Backlog grooming, defer or accept

## References
- [BACKLOG.md](BACKLOG.md) — Actionable tasks linked to debt items
- [ROADMAP.md](ROADMAP.md) — Long-term debt reduction strategy
- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture context
