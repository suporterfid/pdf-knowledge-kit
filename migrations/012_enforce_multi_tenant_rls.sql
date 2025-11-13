-- Migration: enforce consistent multi-tenant RLS policies across tenant scoped tables
--
-- This migration creates a helper function ``app.current_tenant_id()`` that centralises
-- how the application reads the session tenant identifier. It then ensures that all
-- tenant-scoped tables have RLS enabled with policies that require ``tenant_id`` to
-- match ``app.current_tenant_id()`` for both reads (USING) and writes (WITH CHECK).
--
-- Reverting: DROP the ``app.current_tenant_id`` policy from each table and DISABLE RLS.
-- Example: ``DROP POLICY connector_definitions_tenant_isolation ON connector_definitions;``
--          ``ALTER TABLE connector_definitions DISABLE ROW LEVEL SECURITY;``
--          ``DROP FUNCTION IF EXISTS app.current_tenant_id();`` if no longer needed.
--          ``DROP SCHEMA IF EXISTS app CASCADE;`` once no dependant objects remain.
--          Remember to drop the tenant indexes if they cause conflicts when reverting.
--
-- The migration is safe to run multiple times thanks to ``IF EXISTS``/``IF NOT EXISTS``
-- guards around all DDL statements.

CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_tenant_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid;
$$;

DO $$
DECLARE
  rec RECORD;
BEGIN
  FOR rec IN
    SELECT * FROM (VALUES
      ('connector_definitions', 'connector_definitions_tenant_isolation', 'idx_connector_definitions_tenant_id'),
      ('sources', 'sources_tenant_isolation', 'idx_sources_tenant_id'),
      ('ingestion_jobs', 'ingestion_jobs_tenant_isolation', 'idx_ingestion_jobs_tenant_id'),
      ('documents', 'documents_tenant_isolation', 'idx_documents_tenant_id'),
      ('document_versions', 'document_versions_tenant_isolation', 'idx_document_versions_tenant_id'),
      ('chunks', 'chunks_tenant_isolation', 'idx_chunks_tenant_id'),
      ('feedbacks', 'feedbacks_tenant_isolation', 'idx_feedbacks_tenant_id'),
      ('agents', 'agents_tenant_isolation', 'idx_agents_tenant_id'),
      ('agent_versions', 'agent_versions_tenant_isolation', 'idx_agent_versions_tenant_id'),
      ('agent_tests', 'agent_tests_tenant_isolation', 'idx_agent_tests_tenant_id'),
      ('agent_channel_configs', 'agent_channel_configs_tenant_isolation', 'idx_agent_channel_configs_tenant_id'),
      ('conversations', 'conversations_tenant_isolation', 'idx_conversations_tenant_id'),
      ('conversation_participants', 'conversation_participants_tenant_isolation', 'idx_conversation_participants_tenant_id'),
      ('conversation_messages', 'conversation_messages_tenant_isolation', 'idx_conversation_messages_tenant_id')
    ) AS t(table_name, policy_name, index_name)
  LOOP
    -- Ensure the tenant filter index exists for fast lookups
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I (tenant_id);',
      rec.index_name,
      rec.table_name
    );

    -- Enable RLS on the table
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', rec.table_name);

    -- Replace any previous tenant isolation policy with the standard definition
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I;', rec.policy_name, rec.table_name);
    EXECUTE format(
      'CREATE POLICY %I ON %I FOR ALL USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id());',
      rec.policy_name,
      rec.table_name
    );
  END LOOP;
END;
$$;
