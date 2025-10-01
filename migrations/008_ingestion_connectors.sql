-- Extend ingestion entities with connector metadata and document version history
ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS connector_type TEXT,
    ADD COLUMN IF NOT EXISTS credentials BYTEA,
    ADD COLUMN IF NOT EXISTS sync_state JSONB,
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS connector_type TEXT,
    ADD COLUMN IF NOT EXISTS credentials BYTEA,
    ADD COLUMN IF NOT EXISTS sync_state JSONB,
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS metadata JSONB;

CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    version INTEGER NOT NULL,
    bytes BIGINT,
    page_count INT,
    connector_type TEXT,
    credentials BYTEA,
    sync_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, version)
);
