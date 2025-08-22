-- Add missing columns for source management
ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS path TEXT,
    ADD COLUMN IF NOT EXISTS url TEXT,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_sources_path_active ON sources (path) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sources_url_active ON sources (url) WHERE deleted_at IS NULL;
