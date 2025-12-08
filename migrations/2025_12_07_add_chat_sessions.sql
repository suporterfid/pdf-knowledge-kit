-- Migration: Add chat_sessions and chat_session_messages tables for lightweight chat history
-- This migration adds support for persisting chat session history from the frontend chat interface

-- Create chat_sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
  id TEXT PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant_id
  ON chat_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant_created_at
  ON chat_sessions(tenant_id, created_at DESC);

ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'chat_sessions'
      AND policyname = 'chat_sessions_tenant_isolation'
  ) THEN
    CREATE POLICY chat_sessions_tenant_isolation ON chat_sessions
      FOR ALL
      USING (tenant_id = app.current_tenant_id())
      WITH CHECK (tenant_id = app.current_tenant_id());
  END IF;
END;
$$;

-- Create chat_session_messages table
CREATE TABLE IF NOT EXISTS chat_session_messages (
  id TEXT PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_chat_session_messages_tenant_session
  ON chat_session_messages(tenant_id, session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_session_messages_tenant_id
  ON chat_session_messages(tenant_id);

ALTER TABLE chat_session_messages ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'chat_session_messages'
      AND policyname = 'chat_session_messages_tenant_isolation'
  ) THEN
    CREATE POLICY chat_session_messages_tenant_isolation ON chat_session_messages
      FOR ALL
      USING (tenant_id = app.current_tenant_id())
      WITH CHECK (tenant_id = app.current_tenant_id());
  END IF;
END;
$$;

-- Trigger to update chat_sessions.updated_at on message insert
CREATE OR REPLACE FUNCTION update_chat_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE chat_sessions
  SET updated_at = timezone('utc', now())
  WHERE id = NEW.session_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chat_session_messages_update_session_timestamp ON chat_session_messages;
CREATE TRIGGER chat_session_messages_update_session_timestamp
AFTER INSERT ON chat_session_messages
FOR EACH ROW
EXECUTE PROCEDURE update_chat_session_timestamp();
