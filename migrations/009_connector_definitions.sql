-- Create connector definitions catalogue and link it to sources
CREATE TABLE IF NOT EXISTS connector_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    params JSONB,
    credentials BYTEA,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_connector_definitions_type ON connector_definitions (type);

ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS connector_definition_id UUID REFERENCES connector_definitions(id),
    ADD COLUMN IF NOT EXISTS connector_metadata JSONB;
