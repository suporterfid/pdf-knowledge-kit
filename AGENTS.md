# AI Agent Instructions

## Quick Reference
| Task | Prompt |
|------|--------|
| Re-analyze repository | `docs/prompts/01-ANALYSIS.md` |
| Update after changes | `docs/prompts/02-UPDATE.md` |
| Implement next task | `docs/prompts/03-IMPLEMENT.md` |

## Project Context
- **Project**: PDF Knowledge Kit — Multi-tenant RAG platform with semantic search
- **Version**: 1.0.1 (Beta, production-ready)
- **Stack**: FastAPI + React + PostgreSQL + pgvector
- **Architecture**: See `docs/development/ARCHITECTURE.md`
- **Current Status**: See `docs/development/STATUS.md`
- **Task Backlog**: See `docs/development/BACKLOG.md`
- **Technical Debt**: See `docs/development/TECHNICAL_DEBT.md`
- **Coding Standards**: See `docs/TECH_STACK_STANDARDS.md`

## Working Agreements

### Before Any Task
1. **Read AGENTS.md** (this file) to understand project context
2. **Check STATUS.md** for current project state and active work
3. **Review relevant standards** in TECH_STACK_STANDARDS.md for the technology you'll work with
4. **Check BACKLOG.md** to see if your task is already prioritized
5. **Review TECHNICAL_DEBT.md** to avoid introducing known anti-patterns

### During Implementation
1. **Follow established patterns** found in the codebase
   - Backend: Repository pattern, service layer, dependency injection
   - Frontend: Functional components, Context API, custom hooks
2. **Write tests** for new functionality
   - Backend: pytest with fixtures (see `tests/conftest.py`)
   - Frontend: Vitest with React Testing Library
3. **Keep functions focused** — Single Responsibility Principle
   - Target: <50 lines per function
   - If larger, extract helper functions
4. **Handle errors explicitly** — No silent failures
   - Log errors with context (tenant_id, user_id, document_id, etc.)
   - Return appropriate HTTP status codes (400, 404, 403, 500)
5. **Maintain type safety**
   - Python: Use type hints for all public functions
   - TypeScript: No `any` types, use `unknown` and narrow
6. **Respect multi-tenancy** — Always consider tenant isolation
   - Backend: Use tenant context, verify RLS policies
   - Frontend: Include tenant_id in API calls

### After Completing Work
1. **Update BACKLOG.md** — Mark completed items, move to "Completed ✅" section
2. **Update CHANGELOG.md** — Log user-facing changes in [Unreleased] section
   - Use categories: Added, Changed, Fixed, Deprecated, Removed, Security
3. **Update STATUS.md** if project state changed
   - Recent Progress, Active Work, or Key Metrics
4. **Add new technical debt** to TECHNICAL_DEBT.md if you encountered issues
5. **Run quality checks** before committing:
   ```bash
   # Backend
   ruff check --config pyproject.toml .
   black --config pyproject.toml .
   pytest --cov=app

   # Frontend
   cd frontend && npm run lint && npm run test
   ```

## Conventions

### Task Estimation
| Label | Time | Examples |
|-------|------|----------|
| `[S]` | <2 hours | Config change, small bugfix, add test, documentation update |
| `[M]` | 2-8 hours | New endpoint, component, refactor module, add connector |
| `[L]` | 1-3 days | New feature, significant refactor, multi-module change |
| `[XL]` | >3 days | Major feature, architecture change, migration |

### Priority Levels
| Icon | Level | Response Time | Examples |
|------|-------|---------------|----------|
| 🔴 | Critical | Immediate — blocks progress | Security vulnerabilities, data corruption, production outages |
| 🟠 | High | This sprint/week | Missing features blocking users, performance issues, major bugs |
| 🟡 | Medium | Next sprint/soon | Nice-to-have features, refactoring, documentation gaps |
| 🟢 | Low | When convenient | Minor improvements, experimental features, future considerations |

### Commit Messages
Use **Conventional Commits** format:
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code change that neither fixes nor adds
- `test:` Adding or updating tests
- `chore:` Maintenance tasks
- `perf:` Performance improvements

**Examples:**
```
feat(ingestion): add Google Drive connector
fix(auth): prevent infinite refresh loop
docs: update deployment guide for AWS
refactor(rag): extract BM25 reranking to separate function
test(agents): add tests for agent versioning
```

## Stack-Specific Guidelines

### Backend (Python + FastAPI)

#### Project Structure
- **Routers** (`app/routers/`): HTTP endpoint handlers
- **Services** (`app/*/service.py`): Business logic orchestration
- **Repositories** (`app/*/repository.py`): Data access layer
- **Models** (`app/models/`): SQLAlchemy ORM models
- **Core** (`app/core/`): Infrastructure (auth, db, middleware)

#### Common Tasks
**Adding a new endpoint:**
1. Define Pydantic schema in `app/*/schemas.py`
2. Implement handler in `app/routers/*.py`
3. Add service method in `app/*/service.py` if business logic needed
4. Add tests in `tests/test_*.py`
5. Update `docs/development/API_REFERENCE.md`

**Adding a new connector:**
1. Create parser in `app/ingestion/connectors/<name>.py`
2. Extend `IngestionService` to register connector type
3. Add tests in `tests/test_<name>_connector.py`
4. Update documentation

#### Testing Patterns
```python
# Use fixtures for reusable setup
def test_feature(tenant_auth, app_factory):
    tenant_id = tenant_auth["tenant_id"]
    client = app_factory()

    # Arrange
    setup_data(tenant_id)

    # Act
    response = client.post("/api/endpoint", json={...})

    # Assert
    assert response.status_code == 200
    assert response.json()["key"] == "expected"
```

### Frontend (React + TypeScript)

#### Project Structure
- **Components** (`frontend/src/components/`): Reusable UI components
- **Pages** (`frontend/src/*Page.tsx`): Top-level route components
- **Hooks** (`frontend/src/hooks/`): Custom React hooks
- **Auth** (`frontend/src/auth/`): Authentication system
- **Admin** (`frontend/src/admin/`): Admin dashboard

#### Common Tasks
**Adding a new component:**
1. Create `ComponentName.tsx` in appropriate directory
2. Define props interface
3. Implement component with type-safe props
4. Add tests in `ComponentName.test.tsx`
5. Export from index file if needed

**Adding a new page:**
1. Create `PageName.tsx` in `src/`
2. Add route in `App.tsx`
3. Add authentication guard if needed (`RequireAuth`)
4. Test navigation and functionality

#### Component Template
```typescript
import React from 'react';

interface MyComponentProps {
  title: string;
  onAction: () => void;
  isLoading?: boolean;
}

export function MyComponent({ title, onAction, isLoading = false }: MyComponentProps) {
  return (
    <div>
      <h2>{title}</h2>
      <button onClick={onAction} disabled={isLoading}>
        {isLoading ? 'Loading...' : 'Action'}
      </button>
    </div>
  );
}
```

### Database (PostgreSQL)

#### Schema Conventions
- **Tables**: `lowercase_plural` (e.g., `users`, `documents`)
- **Columns**: `lowercase_with_underscores`
- **Primary keys**: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- **Foreign keys**: `{table}_id` (e.g., `user_id`, `organization_id`)
- **Timestamps**: `created_at`, `updated_at` (both `timestamptz`)
- **Tenant column**: `organization_id UUID NOT NULL` for RLS

#### Adding a Migration
1. Create `migrations/NNN_description.sql`
2. Use idempotent SQL (`CREATE IF NOT EXISTS`)
3. Add RLS policies if new tenant-scoped table
4. Test on development database
5. Document in migration comment

#### RLS Policy Template
```sql
-- Enable RLS
ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY tenant_isolation ON my_table
  FOR ALL
  USING (organization_id = app.current_tenant_id());
```

## Multi-Tenancy Checklist

When working with tenant data, ensure:
- [ ] Table has `organization_id UUID NOT NULL` column
- [ ] RLS policy exists and is enabled
- [ ] Service layer uses tenant context
- [ ] Tests verify tenant isolation
- [ ] API endpoints require authentication
- [ ] Queries filter by `organization_id` (even though RLS does it, defense-in-depth)

## Security Checklist

Before merging code that handles:
- [ ] **User input**: Validated with Pydantic or React forms
- [ ] **SQL queries**: Parameterized, no string interpolation
- [ ] **File uploads**: MIME type validation, size limits, virus scanning (if needed)
- [ ] **API keys/secrets**: Stored in environment variables, never in code
- [ ] **Authentication**: JWT validation, expiry checks, role verification
- [ ] **Authorization**: RBAC enforcement, tenant isolation verified

## Performance Checklist

For features involving:
- [ ] **Database queries**: Indexed columns, no N+1 queries, EXPLAIN ANALYZE
- [ ] **API endpoints**: Response time <200ms, pagination for large datasets
- [ ] **File processing**: Streaming for large files, background jobs for slow operations
- [ ] **Frontend**: Code splitting, lazy loading, memoization for expensive computations

## Documentation Updates

After implementing a feature, update relevant docs:
- [ ] `README.md` if user-facing setup changes
- [ ] `docs/development/ARCHITECTURE.md` if system design changes
- [ ] `API_REFERENCE.md` if new endpoints added
- [ ] `DEPLOYMENT.md` if deployment steps change
- [ ] `CHANGELOG.md` for all user-visible changes

## Common Pitfalls

### Backend
❌ **Don't**: Hardcode configuration values
✅ **Do**: Use environment variables with sensible defaults

❌ **Don't**: Return generic error messages
✅ **Do**: Return specific error codes and user-friendly messages

❌ **Don't**: Log sensitive data (passwords, tokens, PII)
✅ **Do**: Log request IDs, tenant IDs, and sanitized inputs

### Frontend
❌ **Don't**: Use `any` type
✅ **Do**: Define proper interfaces or use `unknown` and narrow

❌ **Don't**: Fetch data in `useEffect` without cleanup
✅ **Do**: Use AbortController for cancellable fetches

❌ **Don't**: Store sensitive data in localStorage
✅ **Do**: Store refresh tokens only, access tokens in memory

### Database
❌ **Don't**: Create migrations without rollback plan
✅ **Do**: Document rollback steps in migration comments

❌ **Don't**: Add columns without default values to large tables
✅ **Do**: Add nullable columns or use multiple migrations

## Emergency Procedures

### Production Issue
1. **Check STATUS.md** for known issues
2. **Check logs** in `logs/app.log` or `docker compose logs -f app`
3. **Verify database** connection and RLS configuration
4. **Rollback** if necessary (see `DEPLOYMENT.md`)
5. **Document** the incident and resolution in `docs/incidents/`

### Broken Build
1. **Check CI logs** for specific error
2. **Run quality checks locally** (see "After Completing Work" above)
3. **Fix linting errors** before logic errors
4. **Revert** if fix is complex and blocking others

## Resources

### Documentation
- [README.md](README.md) — User setup and usage
- [ARCHITECTURE.md](docs/development/ARCHITECTURE.md) — System design
- [API_REFERENCE.md](API_REFERENCE.md) — API endpoints
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment guide
- [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) — Frontend development
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) — Operations manual

### Development Tracking
- [STATUS.md](docs/development/STATUS.md) — Current state
- [ROADMAP.md](docs/development/ROADMAP.md) — Future plans
- [BACKLOG.md](docs/development/BACKLOG.md) — Prioritized tasks
- [TECHNICAL_DEBT.md](docs/development/TECHNICAL_DEBT.md) — Known issues
- [CHANGELOG.md](CHANGELOG.md) — Release history

### Standards
- [TECH_STACK_STANDARDS.md](docs/TECH_STACK_STANDARDS.md) — Coding conventions
- [pyproject.toml](pyproject.toml) — Python tool configuration
- [frontend/eslint.config.js](frontend/eslint.config.js) — TypeScript linting

### External References
- FastAPI: https://fastapi.tiangolo.com
- React: https://react.dev
- PostgreSQL: https://www.postgresql.org/docs/
- pgvector: https://github.com/pgvector/pgvector
- Conventional Commits: https://www.conventionalcommits.org/

## Getting Help

1. **Search the codebase** for similar patterns
2. **Check documentation** in `docs/` directory
3. **Review tests** for usage examples
4. **Consult ARCHITECTURE.md** for system design context
5. **Check TECHNICAL_DEBT.md** for known issues and workarounds

## Feedback & Improvements

This file is a living document. If you encounter:
- Missing guidelines
- Outdated information
- Unclear instructions
- Better practices

Please update AGENTS.md and document the change in CHANGELOG.md.
