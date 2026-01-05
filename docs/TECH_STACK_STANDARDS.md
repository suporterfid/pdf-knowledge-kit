# Tech Stack Standards

## Core Technologies

| Purpose | Technology | Version | Documentation |
|---------|------------|---------|---------------|
| Backend Language | Python | 3.10+ | [python.org](https://python.org) |
| Backend Framework | FastAPI | 0.110+ | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| Frontend Language | TypeScript | 5.0+ | [typescriptlang.org](https://www.typescriptlang.org/) |
| Frontend Framework | React | 18.2 | [react.dev](https://react.dev) |
| Frontend Build Tool | Vite | 7.2+ | [vitejs.dev](https://vitejs.dev) |
| Database | PostgreSQL | 15+ | [postgresql.org](https://www.postgresql.org/) |
| ORM | SQLAlchemy | 2.0+ | [sqlalchemy.org](https://www.sqlalchemy.org/) |
| Vector Extension | pgvector | 0.2.5+ | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) |
| Embeddings | fastembed | 0.7.3 | [qdrant.github.io/fastembed](https://qdrant.github.io/fastembed/) |
| Styling | TailwindCSS | 3.4+ | [tailwindcss.com](https://tailwindcss.com) |
| Testing (Backend) | pytest | 8.0+ | [pytest.org](https://pytest.org) |
| Testing (Frontend) | Vitest | 4.0+ | [vitest.dev](https://vitest.dev) |
| Container Runtime | Docker | 24+ | [docker.com](https://www.docker.com/) |
| Orchestration | Docker Compose | 2.x | [docs.docker.com/compose](https://docs.docker.com/compose/) |

## Coding Conventions

### Python (Backend)

#### Style Guide
- **Standard**: [PEP 8](https://peps.python.org/pep-0008/) with Black formatting
- **Line length**: 88 characters (Black default)
- **Quotes**: Double quotes `"` for strings (Black enforced)
- **Imports**: Sorted with `isort` (Ruff integrated)

#### Linting & Formatting
- **Linter**: Ruff (`ruff check --config pyproject.toml .`)
- **Formatter**: Black (`black --config pyproject.toml .`)
- **Type Checker**: mypy (`mypy --config-file pyproject.toml`)
- **Security**: Bandit (`bandit -c pyproject.toml -r app/`)
- **Configuration**: All tools configured in `pyproject.toml`

#### Naming Conventions
- **Modules/packages**: `lowercase_with_underscores` (e.g., `app/ingestion/service.py`)
- **Classes**: `PascalCase` (e.g., `AgentService`, `ConversationRepository`)
- **Functions/methods**: `lowercase_with_underscores` (e.g., `build_context()`, `get_job_status()`)
- **Constants**: `UPPERCASE_WITH_UNDERSCORES` (e.g., `UPLOAD_MAX_SIZE`, `DEFAULT_CHUNK_SIZE`)
- **Private members**: Prefix with single underscore `_` (e.g., `_validate_signature()`)
- **Protected members**: Prefix with double underscore `__` (rare, avoid unless necessary)

#### Type Hints
- **Requirement**: All public functions must have type hints
- **Style**: Use `from typing import` for Python 3.10+ types
- **Return types**: Always specify, including `None`
- **Example**:
  ```python
  from typing import Optional

  def build_context(
      question: str,
      k: int = 5,
      tenant_id: Optional[str] = None
  ) -> tuple[str, list[dict[str, Any]]]:
      """Build RAG context from vector search."""
      pass
  ```

#### Docstrings
- **Style**: Google-style docstrings
- **Requirement**: All public functions, classes, and modules
- **Example**:
  ```python
  def ingest_local(docs_dir: str, tenant_id: str, enable_ocr: bool = False) -> str:
      """Ingest documents from local directory.

      Args:
          docs_dir: Path to directory containing documents
          tenant_id: Organization UUID for multi-tenancy
          enable_ocr: Enable OCR for scanned PDFs (default: False)

      Returns:
          Job ID for tracking ingestion progress

      Raises:
          ValueError: If docs_dir doesn't exist
          PermissionError: If tenant not authorized
      """
      pass
  ```

#### Error Handling
- **Prefer specific exceptions**: Use `ValueError`, `KeyError`, `PermissionError` over generic `Exception`
- **Always log errors**: Use structured logging with context
  ```python
  logger.error(
      "Failed to ingest document",
      extra={"document_id": doc_id, "error": str(e), "tenant_id": tenant_id}
  )
  ```
- **Fail fast**: Validate inputs early, raise exceptions before side effects
- **No silent failures**: Never catch exceptions without logging or re-raising

### TypeScript (Frontend)

#### Style Guide
- **Standard**: [Airbnb React/JSX Style Guide](https://github.com/airbnb/javascript/tree/master/react)
- **Line length**: 100 characters (ESLint configured)
- **Quotes**: Single quotes `'` for strings
- **Semicolons**: Required (ESLint enforced)

#### Linting
- **Linter**: ESLint (`npm run lint`)
- **Configuration**: `eslint.config.js` with TypeScript, React, React Hooks plugins
- **Rules**: TypeScript strict mode, React Hooks exhaustive-deps

#### Naming Conventions
- **Components**: `PascalCase` (e.g., `AuthProvider`, `ChatPage`, `MessageComposer`)
- **Files**: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- **Functions/variables**: `camelCase` (e.g., `useAuth`, `handleSubmit`, `isLoading`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`, `MAX_FILE_SIZE`)
- **Interfaces/types**: `PascalCase` with descriptive names (e.g., `AuthContextValue`, `Message`)

#### Component Structure
- **Functional components**: Use function declarations, not arrow functions
  ```typescript
  export function ChatPage() {
    return <div>...</div>;
  }
  ```
- **Hooks order**: useState → useEffect → useContext → custom hooks
- **Props destructuring**: Destructure in function signature
  ```typescript
  export function Message({ content, author, timestamp }: MessageProps) {
    // ...
  }
  ```

#### Type Safety
- **No `any`**: Use `unknown` if type is truly unknown, then narrow
- **Explicit return types**: For exported functions and hooks
- **Props interfaces**: Define interfaces for all component props
  ```typescript
  interface MessageProps {
    content: string;
    author: string;
    timestamp: Date;
    onDelete?: () => void;  // Optional props with ?
  }
  ```

### SQL

#### Schema Conventions
- **Tables**: `lowercase_plural` (e.g., `users`, `documents`, `chunks`)
- **Columns**: `lowercase_with_underscores` (e.g., `organization_id`, `created_at`)
- **Primary keys**: `id` (UUID type, generated with `gen_random_uuid()`)
- **Foreign keys**: `{table_name}_id` (e.g., `user_id`, `source_id`)
- **Timestamps**: `created_at`, `updated_at` (timestamptz type, default now())
- **Soft deletes**: `deleted_at` (nullable timestamptz)

#### Migration Standards
- **File naming**: `NNN_descriptive_name.sql` (e.g., `001_create_tables.sql`, `012_add_tenant_ids.sql`)
- **Idempotency**: Use `IF NOT EXISTS`, `DROP IF EXISTS`, or transactional DDL
- **Rollback**: Always provide DOWN migration in comments or separate file
- **Testing**: Test migrations on copy of production data before deployment

## File Organization

### Backend (`app/`)
```
app/
├── routers/          # FastAPI route handlers (one file per domain)
├── models/           # SQLAlchemy ORM models
├── core/             # Core infrastructure (auth, db, middleware)
├── security/         # Authentication & authorization
├── agents/           # Agent orchestration system
├── conversations/    # Conversation management
├── channels/         # Communication channel adapters
├── ingestion/        # Document ingestion pipeline
│   ├── parsers/      # Document format parsers
│   └── connectors/   # Remote data source connectors
├── migrations/       # Alembic-style database migrations
└── static/           # Frontend build artifacts
```

### Frontend (`frontend/src/`)
```
src/
├── components/       # Reusable UI components
├── pages/            # Top-level page components
├── auth/             # Authentication system
├── admin/            # Admin dashboard
├── hooks/            # Custom React hooks
├── utils/            # Utility functions
├── types/            # TypeScript type definitions
└── assets/           # Static assets (images, fonts)
```

### Tests (`tests/`)
```
tests/
├── conftest.py       # Shared pytest fixtures
├── test_*.py         # Test files (mirror app/ structure)
└── fixtures/         # Test data and mock objects
```

### Documentation (`docs/`)
```
docs/
├── development/      # Development-specific docs (STATUS, BACKLOG, etc.)
├── prompts/          # AI agent prompt templates
└── TECH_STACK_STANDARDS.md  # This file
```

## Testing Standards

### Backend (pytest)

#### Naming
- **Files**: `test_*.py` or `*_test.py`
- **Functions**: `test_<feature>_<scenario>` (e.g., `test_build_context_with_tenant_id`)
- **Classes**: `Test<Feature>` (e.g., `TestAgentService`)

#### Structure
- **Arrange-Act-Assert**: Clearly separate setup, execution, and validation
- **One assertion focus**: Test one thing at a time (may have multiple asserts for that one thing)
- **Fixtures**: Use pytest fixtures for reusable setup (see `tests/conftest.py`)

#### Coverage Target
- **Minimum**: 60% overall coverage
- **Critical paths**: 90%+ coverage (auth, multi-tenancy, payment logic)
- **Run**: `pytest --cov=app --cov-report=html`

#### Example
```python
def test_build_context_filters_by_tenant(tenant_auth):
    """RAG context should only include chunks from the specified tenant."""
    # Arrange
    tenant_id = tenant_auth["tenant_id"]
    other_tenant_id = str(uuid4())
    create_chunk("Tenant A content", tenant_id)
    create_chunk("Tenant B content", other_tenant_id)

    # Act
    context, sources = build_context("test query", k=5, tenant_id=tenant_id)

    # Assert
    assert "Tenant A content" in context
    assert "Tenant B content" not in context
    assert len(sources) == 1
```

### Frontend (Vitest + React Testing Library)

#### Naming
- **Files**: `*.test.tsx` or `*.test.ts` (co-located with components)
- **Functions**: `test('<component> <behavior>')` or `it('<behavior>')`

#### Structure
- **Render**: Use `@testing-library/react` for rendering
- **Query**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
- **Events**: Use `userEvent` for interactions (more realistic than `fireEvent`)

#### Example
```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Message } from './Message';

test('Message displays author and content', () => {
  render(<Message author="Alice" content="Hello world" timestamp={new Date()} />);

  expect(screen.getByText('Alice')).toBeInTheDocument();
  expect(screen.getByText('Hello world')).toBeInTheDocument();
});

test('Message calls onDelete when delete button clicked', async () => {
  const handleDelete = vi.fn();
  render(<Message author="Alice" content="Test" onDelete={handleDelete} />);

  const deleteButton = screen.getByRole('button', { name: /delete/i });
  await userEvent.click(deleteButton);

  expect(handleDelete).toHaveBeenCalledTimes(1);
});
```

## Git Conventions

### Branch Naming
- **Feature**: `feature/<short-description>` (e.g., `feature/google-drive-connector`)
- **Bugfix**: `fix/<issue-or-description>` (e.g., `fix/ocr-memory-leak`)
- **Hotfix**: `hotfix/<critical-issue>` (e.g., `hotfix/security-patch-jwt`)
- **Release**: `release/v<major>.<minor>.<patch>` (e.g., `release/v1.1.0`)
- **Experimental**: `experiment/<description>` (e.g., `experiment/hnw-indexing`)

### Commit Messages
- **Format**: Conventional Commits ([conventionalcommits.org](https://www.conventionalcommits.org/))
- **Structure**: `<type>(<scope>): <description>`
- **Types**:
  - `feat:` New feature
  - `fix:` Bug fix
  - `docs:` Documentation changes
  - `style:` Formatting, missing semicolons (no code change)
  - `refactor:` Code restructuring (no behavior change)
  - `test:` Adding or updating tests
  - `chore:` Maintenance tasks (deps, CI, build)
  - `perf:` Performance improvements
  - `ci:` CI/CD pipeline changes
- **Scope**: Optional, indicates affected module (e.g., `auth`, `ingestion`, `frontend`)
- **Description**: Imperative mood, lowercase, no period

#### Examples
```
feat(ingestion): add Google Drive connector
fix(auth): prevent infinite refresh loop
docs: update deployment guide for AWS
refactor(rag): extract BM25 reranking to separate function
test(agents): add tests for agent versioning
chore(deps): upgrade FastAPI to 0.110
```

### Pull Request Requirements
- **Title**: Same format as commit messages
- **Description**: What, why, and how (use PR template)
- **Checklist**:
  - [ ] Tests added/updated
  - [ ] Documentation updated
  - [ ] CHANGELOG.md updated (for user-facing changes)
  - [ ] No linting errors (`ruff check`, `npm run lint`)
  - [ ] All tests passing (`pytest`, `npm run test`)
- **Reviewers**: Minimum 1 approval required
- **CI**: All checks must pass (tests, linting, security scans)

## Code Quality Tools

### Automated Checks
- **Pre-commit**: Recommended (Black, Ruff, mypy)
- **CI/CD**: GitHub Actions for automated testing and deployment
- **Dependency scanning**: Dependabot for security updates
- **Code coverage**: Codecov or similar for tracking test coverage

### Quality Gates
| Tool | Purpose | Threshold |
|------|---------|-----------|
| Ruff | Linting (Python) | Zero errors |
| Black | Formatting (Python) | Must pass |
| mypy | Type checking (Python) | Zero errors (with exceptions) |
| Bandit | Security (Python) | Zero high/critical issues |
| ESLint | Linting (TypeScript) | Zero errors |
| pytest | Unit tests (Python) | 60%+ coverage |
| Vitest | Unit tests (TypeScript) | 60%+ coverage |

### Running Quality Checks
```bash
# Backend
ruff check --config pyproject.toml .
black --check --config pyproject.toml .
mypy --config-file pyproject.toml
bandit -c pyproject.toml -r app/
pytest --cov=app --cov-report=html

# Frontend
cd frontend
npm run lint
npm run test
npm run build  # Ensure production build succeeds
```

## Performance Guidelines

### Backend
- **Database queries**: Use indexes, avoid N+1 queries
- **Async operations**: Use `async def` for I/O-bound operations
- **Connection pooling**: Configure pgbouncer for production
- **Caching**: Use Redis for frequently accessed data (not yet implemented)

### Frontend
- **Code splitting**: Use `React.lazy()` for route-based splitting
- **Memoization**: Use `React.memo`, `useMemo`, `useCallback` judiciously
- **Bundle size**: Monitor with `vite-plugin-analyzer`
- **Images**: Optimize and use WebP format

## Security Best Practices

### Authentication
- **Passwords**: Argon2 hashing (configured in `app/security/passwords.py`)
- **Tokens**: HS256 JWT (or RS256 for distributed systems)
- **Expiry**: Short-lived access tokens (15 min), long-lived refresh tokens (7 days)

### Authorization
- **RBAC**: Role-based access control (viewer, operator, admin)
- **RLS**: Row-Level Security for multi-tenancy
- **Least privilege**: Grant minimum permissions necessary

### Input Validation
- **Backend**: Pydantic models for all API inputs
- **Frontend**: React forms with validation
- **SQL**: Parameterized queries only (no string interpolation)
- **XSS**: DOMPurify for sanitizing markdown HTML

### Secrets Management
- **Environment variables**: Use `.env` files (never commit)
- **Production**: Use secret managers (AWS Secrets Manager, HashiCorp Vault)
- **Rotation**: Implement key rotation for API keys and tokens

## Accessibility Guidelines

### Frontend
- **Semantic HTML**: Use proper heading hierarchy, `<nav>`, `<main>`, `<aside>`
- **ARIA**: Add ARIA labels for screen readers where necessary
- **Keyboard navigation**: Ensure all interactive elements are keyboard accessible
- **Color contrast**: WCAG AA minimum (4.5:1 for normal text, 3:1 for large text)
- **Testing**: Use axe DevTools or Lighthouse for automated audits

## Documentation Standards

### Code Documentation
- **Public APIs**: Always document with docstrings/JSDoc
- **Complex logic**: Add inline comments explaining "why", not "what"
- **TODOs**: Use `TODO(username):` format with context

### Project Documentation
- **README.md**: User-facing setup and usage guide
- **ARCHITECTURE.md**: System design and technical details
- **API_REFERENCE.md**: Complete API endpoint documentation
- **DEPLOYMENT.md**: Step-by-step deployment instructions

## Deprecation Policy

### Deprecating Features
1. **Announce**: Document in CHANGELOG.md with deprecation notice
2. **Warning**: Log deprecation warnings in code
3. **Timeline**: Provide at least 2 minor versions before removal
4. **Migration**: Provide migration guide and alternative

### Example
```python
import warnings

def old_function():
    warnings.warn(
        "old_function is deprecated, use new_function instead",
        DeprecationWarning,
        stacklevel=2
    )
    return new_function()
```

## References
- [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Airbnb React/JSX Style Guide](https://github.com/airbnb/javascript/tree/master/react)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Semantic Versioning](https://semver.org/)
