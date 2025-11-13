-- Base schema for the knowledge kit database.
--
-- The schema is intentionally idempotent so that ``ensure_schema`` can run the
-- file on every startup. Tables are defined with ``IF NOT EXISTS`` clauses and
-- column defaults mirror the latest migrations, ensuring that fresh installs do
-- not rely on incremental migrations to get the correct shape.

-- Required extensions -------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid
CREATE EXTENSION IF NOT EXISTS vector;

-- Multi-tenant core ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  subdomain TEXT NOT NULL,
  plan_type TEXT NOT NULL DEFAULT 'free'
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_organizations_subdomain_unique
  ON organizations (subdomain);

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'viewer',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_organization_id ON users (organization_id);

CREATE TABLE IF NOT EXISTS user_invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email VARCHAR(320) NOT NULL,
  role VARCHAR(32) NOT NULL,
  token VARCHAR(255) NOT NULL,
  message TEXT,
  expires_at TIMESTAMPTZ NOT NULL,
  accepted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_invites_token_unique
  ON user_invites (token);
CREATE INDEX IF NOT EXISTS ix_user_invites_org ON user_invites (organization_id);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(255) NOT NULL,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  user_agent VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash
  ON refresh_tokens (token_hash);

-- Connector definitions -----------------------------------------------------
CREATE TABLE IF NOT EXISTS connector_definitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  description TEXT,
  params JSONB,
  credentials BYTEA,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_connector_definitions_tenant_type
  ON connector_definitions (tenant_id, type);

-- Ingestion sources ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  label TEXT,
  location TEXT,
  path TEXT,
  url TEXT,
  params JSONB,
  connector_type TEXT,
  connector_definition_id UUID REFERENCES connector_definitions(id),
  connector_metadata JSONB,
  credentials BYTEA,
  sync_state JSONB,
  version INTEGER NOT NULL DEFAULT 1,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sources_tenant_active
  ON sources (tenant_id, active);
CREATE INDEX IF NOT EXISTS idx_sources_tenant_path_active
  ON sources (tenant_id, path)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sources_tenant_url_active
  ON sources (tenant_id, url)
  WHERE deleted_at IS NULL;

-- Ingestion jobs ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_tenant_status
  ON ingestion_jobs (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_tenant_source
  ON ingestion_jobs (tenant_id, source_id);

-- Documents -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
  path TEXT NOT NULL,
  bytes BIGINT,
  page_count INT,
  connector_type TEXT,
  credentials BYTEA,
  sync_state JSONB,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_tenant_path
  ON documents (tenant_id, path);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_source
  ON documents (tenant_id, source_id);

-- Document history ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_document_versions_tenant_document
  ON document_versions (tenant_id, document_id);

-- Chunks --------------------------------------------------------------------
-- Dimensão 384 para o modelo 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  token_est INT,
  metadata JSONB,
  embedding VECTOR(384),
  UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_tenant_doc
  ON chunks (tenant_id, doc_id, chunk_index);
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- User feedback -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedbacks (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  helpful BOOLEAN NOT NULL,
  question TEXT,
  answer TEXT,
  session_id TEXT,
  sources JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedbacks_tenant_created_at
  ON feedbacks (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_tenant_helpful
  ON feedbacks (tenant_id, helpful);

-- Agent registry ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_agents_tenant_slug
  ON agents (tenant_id, slug);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_active
  ON agents (tenant_id, is_active);

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
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_agent_versions_tenant_agent
  ON agent_versions(tenant_id, agent_id);

CREATE TABLE IF NOT EXISTS agent_tests (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_agent_tests_tenant_agent
  ON agent_tests(tenant_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tests_tenant_agent_version
  ON agent_tests(tenant_id, agent_version_id);

-- Agent channel configuration ------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_channel_configs (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agent_id BIGINT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  webhook_secret TEXT,
  credentials JSONB NOT NULL DEFAULT '{}'::jsonb,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(agent_id, channel)
);

CREATE INDEX IF NOT EXISTS idx_agent_channel_configs_tenant_agent
  ON agent_channel_configs(tenant_id, agent_id);

CREATE OR REPLACE FUNCTION set_agent_channel_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS agent_channel_configs_updated_at ON agent_channel_configs;
CREATE TRIGGER agent_channel_configs_updated_at
BEFORE UPDATE ON agent_channel_configs
FOR EACH ROW
EXECUTE PROCEDURE set_agent_channel_configs_updated_at();

-- Conversations --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agent_id BIGINT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  external_conversation_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  is_escalated BOOLEAN NOT NULL DEFAULT FALSE,
  escalation_reason TEXT,
  escalated_at TIMESTAMPTZ,
  follow_up_at TIMESTAMPTZ,
  follow_up_note TEXT,
  last_message_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(agent_id, channel, external_conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_tenant_agent
  ON conversations(tenant_id, agent_id, channel);
CREATE INDEX IF NOT EXISTS idx_conversations_tenant_follow_up
  ON conversations(tenant_id, follow_up_at)
  WHERE follow_up_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_tenant_escalated
  ON conversations(tenant_id, is_escalated)
  WHERE is_escalated;

CREATE OR REPLACE FUNCTION set_conversations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS conversations_updated_at ON conversations;
CREATE TRIGGER conversations_updated_at
BEFORE UPDATE ON conversations
FOR EACH ROW
EXECUTE PROCEDURE set_conversations_updated_at();

CREATE TABLE IF NOT EXISTS conversation_participants (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  external_id TEXT,
  display_name TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_participants_tenant_conversation
  ON conversation_participants(tenant_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversation_participants_tenant_role
  ON conversation_participants(tenant_id, conversation_id, role);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  participant_id BIGINT REFERENCES conversation_participants(id) ON DELETE SET NULL,
  direction TEXT NOT NULL,
  body JSONB NOT NULL DEFAULT '{}'::jsonb,
  nlp JSONB NOT NULL DEFAULT '{}'::jsonb,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_tenant_conversation
  ON conversation_messages(tenant_id, conversation_id, sent_at);
