-- Enable pgcrypto for gen_random_uuid
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Table to track content sources for ingestion
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    path TEXT,
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Ensure fast lookups and uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_path ON sources (path) WHERE path IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_url ON sources (url) WHERE url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources (created_at);

-- Table to register ingestion jobs
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_source ON ingestion_jobs (source_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_created_at ON ingestion_jobs (created_at);
