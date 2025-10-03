-- Migration: introduce channel configuration and conversation tables
BEGIN;

CREATE TABLE IF NOT EXISTS agent_channel_configs (
  id BIGSERIAL PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS conversations (
  id BIGSERIAL PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversations(agent_id, channel);
CREATE INDEX IF NOT EXISTS idx_conversations_follow_up ON conversations(follow_up_at) WHERE follow_up_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_escalated ON conversations(is_escalated) WHERE is_escalated;

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
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  external_id TEXT,
  display_name TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_participants_conversation ON conversation_participants(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversation_participants_role ON conversation_participants(conversation_id, role);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  participant_id BIGINT REFERENCES conversation_participants(id) ON DELETE SET NULL,
  direction TEXT NOT NULL,
  body JSONB NOT NULL DEFAULT '{}'::jsonb,
  nlp JSONB NOT NULL DEFAULT '{}'::jsonb,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation ON conversation_messages(conversation_id, sent_at);

COMMIT;
