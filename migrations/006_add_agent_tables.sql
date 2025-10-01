CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    persona JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_template TEXT,
    response_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    deployment_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION set_agents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS agents_updated_at ON agents;
CREATE TRIGGER agents_updated_at
BEFORE UPDATE ON agents
FOR EACH ROW
EXECUTE PROCEDURE set_agents_updated_at();

CREATE TABLE IF NOT EXISTS agent_versions (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    label TEXT,
    created_by TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_template TEXT,
    persona JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(agent_id, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_id ON agent_versions(agent_id);

CREATE TABLE IF NOT EXISTS agent_tests (
    id BIGSERIAL PRIMARY KEY,
    agent_version_id BIGINT REFERENCES agent_versions(id) ON DELETE CASCADE,
    agent_id BIGINT REFERENCES agents(id) ON DELETE CASCADE,
    input_prompt TEXT NOT NULL,
    expected_behavior TEXT,
    response JSONB,
    metrics JSONB,
    status TEXT NOT NULL DEFAULT 'pending',
    channel TEXT,
    ran_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_tests_agent_id ON agent_tests(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tests_agent_version_id ON agent_tests(agent_version_id);
