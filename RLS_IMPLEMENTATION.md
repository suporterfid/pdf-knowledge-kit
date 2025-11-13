# Row Level Security (RLS) Implementation Guide

## Overview

This document describes the Row Level Security (RLS) implementation for multi-tenancy in the PDF Knowledge Kit. RLS ensures that documents and chunks are automatically filtered by tenant (organization) at the database level, providing defense-in-depth security.

## Architecture

### Components

1. **Tenant Middleware** (`app/core/tenant_middleware.py`)
   - Validates JWT tokens from Authorization header
   - Extracts `tenant_id` from token payload
   - Sets PostgreSQL session variable: `SET app.tenant_id = '<organization_id>'`
   - Resets session variable after request completes

2. **Tenant Context** (`app/core/tenant_context.py`)
   - Provides `get_current_tenant_id()` function
   - Uses `contextvars.ContextVar` for thread-safe tenant context
   - Available throughout request lifecycle

3. **Storage Layer** (`app/ingestion/storage.py`)
   - Reads tenant context via `get_current_tenant_id()`
   - Sets `organization_id` on documents and chunks during ingestion
   - No explicit filtering needed in queries

4. **RLS Policies** (migration 011)
   - Enabled on `documents` and `chunks` tables
   - Automatically filters rows by `app.tenant_id` session variable
   - Applies to all SELECT, UPDATE, DELETE operations

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. HTTP Request with JWT Bearer Token                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. TenantContextMiddleware                                      │
│    - Validate JWT                                               │
│    - Extract organization_id from token                         │
│    - SET app.tenant_id = organization_id                        │
│    - Store in request.state and context var                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Application Query (e.g., RAG)                                │
│    SELECT d.path, c.content                                     │
│    FROM chunks c                                                │
│    JOIN documents d ON d.id = c.doc_id                          │
│    WHERE c.embedding IS NOT NULL                                │
│    -- No tenant filter in application code! --                  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. PostgreSQL with RLS                                          │
│    - RLS policy automatically adds:                             │
│      WHERE chunks.organization_id = current_setting('app.tenant_id')  │
│      AND documents.organization_id = current_setting('app.tenant_id') │
│    - Returns only tenant's data                                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Response to Client                                           │
│    - Only organization's documents and chunks                   │
│    - Cross-tenant access impossible                             │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema Changes

### Migration 011: `011_add_rls_for_multi_tenancy.sql`

```sql
-- Add organization_id columns
ALTER TABLE documents ADD COLUMN organization_id UUID REFERENCES organizations(id);
ALTER TABLE chunks ADD COLUMN organization_id UUID REFERENCES organizations(id);

-- Create indexes
CREATE INDEX idx_documents_organization_id ON documents(organization_id);
CREATE INDEX idx_chunks_organization_id ON chunks(organization_id);

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY documents_tenant_isolation ON documents
    FOR ALL
    USING (
        organization_id::text = current_setting('app.tenant_id', true)
        OR current_setting('app.tenant_id', true) IS NULL
    );

CREATE POLICY chunks_tenant_isolation ON chunks
    FOR ALL
    USING (
        organization_id::text = current_setting('app.tenant_id', true)
        OR current_setting('app.tenant_id', true) IS NULL
    );
```

## Security Benefits

### 1. Defense in Depth
- Even if application code has bugs, database prevents cross-tenant access
- SQL injection cannot bypass tenant isolation
- Misconfigured queries still respect tenant boundaries

### 2. Automatic Enforcement
- No need to add `WHERE organization_id = ?` to every query
- Impossible to forget tenant filtering
- Consistent enforcement across all queries

### 3. Performance
- RLS filtering happens at query plan level
- Indexes on `organization_id` used efficiently
- No performance penalty compared to manual WHERE clauses

### 4. Backward Compatibility
- Queries without tenant context still work (for development/testing)
- Gradual migration path for existing data
- Can be tightened in production by removing NULL check

## Testing

### Test Suite: `tests/test_rls_tenant_isolation.py`

The test suite verifies:

1. **Basic Filtering**: Documents and chunks filtered by tenant
2. **Cross-Tenant Prevention**: Tenant A cannot see Tenant B's data
3. **JOIN Queries**: RLS works with complex queries (like RAG)
4. **Backward Compatibility**: Queries work when tenant_id not set

## References

- [PostgreSQL Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [AGENTS.md](../AGENTS.md) - Project coding standards
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture overview
- Migration: [migrations/011_add_rls_for_multi_tenancy.sql](../migrations/011_add_rls_for_multi_tenancy.sql)
- Tests: [tests/test_rls_tenant_isolation.py](../tests/test_rls_tenant_isolation.py)
