# Docker Initialization Error Fixes - Summary

## Issue Description
When starting the application with Docker Compose, several errors were observed:
1. Frontend proxy errors (ECONNREFUSED) when trying to connect to the API
2. "Source not found for tenant" errors during document ingestion
3. PostgreSQL warnings about "there is already a transaction in progress"

## Root Causes

### 1. Frontend Proxy Error
The Vite development server was trying to proxy requests to the backend API before it was ready, resulting in ECONNREFUSED errors. The proxy had no error handling to gracefully handle this startup race condition.

### 2. Source Not Found Error
The `ingest_local()` and `ingest_urls()` functions were creating sources and jobs in one database connection context, then immediately starting a worker thread with a new connection. There was a race condition where the worker would try to reference the source_id before the transaction was committed.

### 3. PostgreSQL Transaction Warnings
Multiple functions in `app/ingestion/storage.py` were using `with conn.transaction()` to create explicit transaction blocks. However, psycopg3's connection context manager already manages transactions automatically. When these functions were called within a connection context manager (e.g., from `connect_and_init()`), psycopg3 would create nested transactions using SAVEPOINTs, which caused PostgreSQL to warn about "there is already a transaction in progress".

## Changes Made

### File: `frontend/vite.config.ts`
Added error handling to the Vite proxy configuration:
- Added `configure` callback with error handler for both `/api` and `/uploads` proxies
- Error handler logs helpful messages and returns 503 status with a user-friendly JSON response
- Added request logging for debugging proxy issues

### File: `app/ingestion/service.py`
Added explicit transaction commits in two functions:
- `ingest_local()`: Added `conn.commit()` after creating source and job (line ~746)
- `ingest_urls()`: Added `conn.commit()` after creating source and job (line ~935)

These ensures the source and job records are persisted to the database before the worker thread starts and tries to reference them.

### File: `app/ingestion/storage.py`
Removed nested `with conn.transaction()` blocks from the following functions:
- `get_or_create_source()`
- `create_connector_definition()`
- `update_connector_definition()`
- `delete_connector_definition()`
- `create_job()`
- `update_job_status()`
- `update_job_params()`
- `update_source()`
- `soft_delete_source()`
- `upsert_document()`
- `insert_chunks()`
- `update_sync_state()`

Added comments explaining that explicit transactions are not needed since the connection context manager already handles commit/rollback.

## Technical Details

### psycopg3 Connection Management
In psycopg3 (version 3.1+):
- `with psycopg.connect(url) as conn:` automatically manages transactions
- The connection starts in a transaction (autocommit=False by default)
- On successful exit from the context, the transaction is committed
- On exception, the transaction is rolled back
- Calling `with conn.transaction()` within an existing transaction creates a SAVEPOINT

### Transaction Best Practices
For the patterns used in this codebase:
1. Use `with psycopg.connect(url) as conn:` for automatic transaction management
2. Call `conn.commit()` explicitly when you need to ensure data is persisted before the context exits
3. Avoid `with conn.transaction()` when already within a connection context manager
4. Use `with conn.transaction()` only when you specifically need a savepoint for partial rollback

## Expected Results

After these changes:
1. ✅ Frontend proxy errors will be handled gracefully with helpful 503 responses
2. ✅ "Source not found" errors during ingestion should be eliminated
3. ✅ PostgreSQL transaction warnings should no longer appear in logs

## Testing Recommendations

To verify the fixes:
1. Start the application with `docker compose up`
2. Monitor logs for the previously observed errors
3. Verify that document ingestion completes successfully
4. Check that the frontend can communicate with the backend API
5. Confirm no PostgreSQL transaction warnings appear

## Additional Notes

- These changes maintain backward compatibility with existing functionality
- No API changes were made
- All changes are internal to implementation details
- Python syntax has been validated with `python3 -m py_compile`
