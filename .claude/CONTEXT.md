# PDF Knowledge Kit - Project Context for Claude Code

## Project Summary
PDF Knowledge Kit is a production-ready, multi-tenant RAG (Retrieval-Augmented Generation) platform that enables semantic search and AI-powered chat over documents. It combines document ingestion, vector search with pgvector, and optional LLM integration.

**Version**: 1.0.1
**License**: MIT
**Python**: 3.11+
**Node**: 18+

## Core Technologies

### Backend Stack
- **Framework**: FastAPI with async/await patterns
- **Database**: PostgreSQL 16 with pgvector extension for vector similarity search
- **ORM**: SQLAlchemy 2.0 with psycopg3 driver
- **Embeddings**: fastembed library with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model
- **LLM Integration**: OpenAI API (optional, for chat responses)
- **Authentication**: JWT-based multi-tenant authentication
- **Testing**: pytest with coverage reporting
- **Code Quality**: ruff (linting), black (formatting), mypy (type checking), bandit (security)

### Frontend Stack
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite 5
- **Styling**: Tailwind CSS
- **State Management**: React Context API
- **HTTP**: Fetch API with streaming support (Server-Sent Events)
- **Testing**: Vitest + Testing Library
- **UI Features**: Dark/light theme, Markdown rendering with syntax highlighting

## Architecture Overview

### Multi-Tenancy Model
- **Tenant Isolation**: Row Level Security (RLS) at PostgreSQL level
- **Authentication Flow**: JWT tokens with tenant_id claim → Middleware sets session variable → RLS policies filter data
- **Organization Management**: Admin can create tenants, invite users, manage API keys
- **Security**: Each request is scoped to a single tenant, no cross-tenant data access

### Document Ingestion Pipeline
1. **Sources**: Local files (PDF, Markdown, CSV, XLSX), URLs, databases (SQL), REST APIs, transcriptions
2. **Processing**:
   - Text extraction (pdfplumber for PDF, optional tesseract OCR)
   - Chunking with overlap (configurable size)
   - Embedding generation (768-dimensional vectors)
   - Storage in PostgreSQL with metadata
3. **Job Tracking**: Async jobs with status, logs, and version history

### RAG (Retrieval-Augmented Generation)
1. **Query**: User question + optional uploaded files
2. **Retrieval**: Vector similarity search (cosine distance) + optional BM25 fallback
3. **Augmentation**: Retrieved chunks provide context
4. **Generation**: Optional OpenAI completion or direct chunk return
5. **Streaming**: SSE for real-time response delivery

## Key Directories

```
pdf-knowledge-kit/
├── app/                      # FastAPI backend application
│   ├── agents/              # Agent management (prompts, providers, versions)
│   ├── conversations/       # Chat/conversation logic
│   ├── core/               # Core utilities (config, db, tenant middleware)
│   ├── ingestion/          # Document processing pipeline
│   │   ├── connectors/     # Source connectors (DB, API, transcription)
│   │   ├── processors/     # Document processors (PDF, MD, etc.)
│   │   └── service.py      # Main ingestion orchestration
│   ├── routers/            # API route handlers
│   │   ├── admin.py        # Admin endpoints (ingestion, jobs)
│   │   ├── chat.py         # Chat endpoints (ask, stream)
│   │   └── tenant.py       # Auth and tenant management
│   ├── rag.py              # RAG query logic
│   ├── main.py             # FastAPI app initialization
│   └── __version__.py      # Version number
├── frontend/                # React TypeScript frontend
│   ├── src/
│   │   ├── auth/           # Authentication context and components
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Page components (Login, Chat, Admin)
│   │   ├── apiKey.tsx      # API key management
│   │   ├── chat.tsx        # Chat state management
│   │   ├── config.tsx      # App configuration
│   │   └── theme.tsx       # Theme management
│   ├── vite.config.ts      # Vite configuration
│   └── package.json        # Frontend dependencies
├── migrations/              # Database migration SQL scripts
├── tests/                   # Backend and frontend tests
├── tools/                   # Utility scripts
├── docs/                    # Documentation and issue tracking
├── schema.sql              # Base database schema (idempotent)
├── seed.py                 # Bootstrap demo tenant and data
├── ingest.py               # CLI for document ingestion
├── query.py                # CLI for testing queries
├── docker-compose.yml      # Production container setup
├── docker-compose.dev.yml  # Development overrides
├── Dockerfile              # Production build
├── Dockerfile.dev          # Development build
└── .env.example            # Environment template
```

## Environment Configuration

### Critical Variables
- `DATABASE_URL` or `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`: Database connection
- `TENANT_TOKEN_SECRET`: Secret for signing JWT tokens (must be secure in production)
- `OPENAI_API_KEY`: Optional, for LLM chat responses
- `DOCS_DIR`: Directory to scan for documents during seed
- `LOG_LEVEL`: INFO, DEBUG, WARNING, ERROR
- `ENABLE_OCR`: Set to 1 to enable OCR for scanned PDFs

### Development Defaults
- Database: `pdfkb` user/password on localhost:5432
- Demo tenant: organization "Demo Tenant" with subdomain "demo"
- Demo user: admin@demo.local / ChangeMe123!

## Development Workflow

### Starting Development Environment
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
- Database: localhost:5432
- Backend API: localhost:8000 (with hot-reload)
- Frontend: localhost:5173 (with HMR)

### Running Tests
```bash
# Backend
pytest -v

# Frontend
cd frontend && npm test
```

### Code Quality
```bash
# Linting and formatting
ruff check app/ tests/
black app/ tests/
mypy app/

# Security scanning
bandit -r app/
```

## Common Tasks

### Adding a New API Endpoint
1. Create route handler in `app/routers/`
2. Add Pydantic schemas for request/response
3. Implement business logic (keep routers thin)
4. Add tests in `tests/`
5. Update API_REFERENCE.md

### Adding a New Document Connector
1. Create connector class in `app/ingestion/connectors/`
2. Implement required methods (fetch_documents, etc.)
3. Register in connector catalog
4. Add tests with mock data
5. Update documentation

### Database Schema Changes
1. Create migration in `migrations/XXX_description.sql`
2. Test migration on local database
3. Update `schema.sql` if needed
4. Run migration on all environments
5. Update models if ORM used

## Testing Strategy

### Backend Tests (pytest)
- Unit tests: Individual functions and classes
- Integration tests: API endpoints with test database
- Connector tests: Mock external services
- Coverage target: >80%

### Frontend Tests (vitest)
- Component tests: UI behavior
- Integration tests: Context providers
- API mocks: MSW (Mock Service Worker)

## Security Considerations

### Multi-Tenant Isolation
- RLS enforced at database level (defense in depth)
- JWT validation on every request
- Tenant context propagated through middleware
- No direct SQL queries without tenant filter

### Authentication
- Passwords hashed with secure algorithm (Argon2/bcrypt)
- JWT tokens with expiration
- Refresh token rotation
- Rate limiting on auth endpoints

### Data Protection
- Sensitive credentials stored in environment variables
- API keys scoped to organizations
- File uploads limited by size and type
- Input validation on all endpoints

## Performance Optimization

### Vector Search
- pgvector index on embeddings (IVFFLAT or HNSW)
- Configurable k parameter for top-k results
- Optional BM25 hybrid search for keyword matching

### Caching
- Embedding model loaded once at startup
- Database connection pooling
- Static asset caching

### Scalability
- Stateless API (horizontal scaling ready)
- Async I/O for network operations
- Background job processing
- Separate frontend serving (CDN-ready)

## Troubleshooting

### Common Issues

**Frontend can't connect to API**
- Check proxy configuration in vite.config.ts
- Verify CORS settings in backend
- Check network aliases in Docker

**Database connection errors**
- Verify DATABASE_URL format
- Check postgres container health
- Ensure pgvector extension enabled

**Slow queries**
- Check vector index exists
- Analyze query plans
- Tune pgvector parameters

**OCR not working**
- Verify tesseract installed
- Check language packs
- Enable ENABLE_OCR=1

## Release Process

1. Update version in `app/__version__.py`
2. Update CHANGELOG.md
3. Run full test suite
4. Build production images
5. Tag release in git
6. Deploy to staging
7. Run smoke tests
8. Deploy to production
9. Monitor logs and metrics

## Resources

- **Main Documentation**: README.md, PROJECT_OVERVIEW.md, ARCHITECTURE.md
- **API Reference**: API_REFERENCE.md (auto-generated from FastAPI)
- **Operations**: OPERATOR_GUIDE.md, DISASTER_RECOVERY_RUNBOOK.md
- **Contributing**: CONTRIBUTING.md
- **Frontend Guide**: FRONTEND_GUIDE.md
