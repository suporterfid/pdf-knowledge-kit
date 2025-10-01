-- Base schema for the knowledge kit database.
--
-- The schema is intentionally idempotent so that ``ensure_schema`` can run the
-- file on every startup. Tables are defined with ``IF NOT EXISTS`` clauses and
-- column defaults mirror the latest migrations, ensuring that fresh installs do
-- not rely on incremental migrations to get the correct shape.

-- Required extensions -------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid
CREATE EXTENSION IF NOT EXISTS vector;

-- Ingestion sources ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,
  label TEXT,
  location TEXT,
  path TEXT,
  url TEXT,
  params JSONB,
  connector_type TEXT,
  credentials BYTEA,
  sync_state JSONB,
  version INTEGER NOT NULL DEFAULT 1,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sources_active ON sources (active);
CREATE INDEX IF NOT EXISTS idx_sources_path_active ON sources (path) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sources_url_active ON sources (url) WHERE deleted_at IS NULL;

-- Ingestion jobs ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  params JSONB,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  log_path TEXT,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs (status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_source_id ON ingestion_jobs (source_id);

-- Documents -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY,
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
  path TEXT NOT NULL UNIQUE,
  bytes BIGINT,
  page_count INT,
  connector_type TEXT,
  credentials BYTEA,
  sync_state JSONB,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Document history ----------------------------------------------------------
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

-- Chunks --------------------------------------------------------------------
-- Dimensão 384 para o modelo 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  token_est INT,
  metadata JSONB,
  embedding VECTOR(384),
  UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (doc_id, chunk_index);
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- User feedback -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedbacks (
  id UUID PRIMARY KEY,
  helpful BOOLEAN NOT NULL,
  question TEXT,
  answer TEXT,
  session_id TEXT,
  sources JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_helpful ON feedbacks (helpful);

-- Agent registry ------------------------------------------------------------
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
