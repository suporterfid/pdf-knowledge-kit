-- Migration: Add organization_id to documents and chunks tables and enable Row Level Security
-- This migration implements tenant isolation by:
-- 1. Adding organization_id columns to documents and chunks tables
-- 2. Enabling Row Level Security (RLS) on these tables
-- 3. Creating policies that filter rows based on the session variable app.tenant_id
--
-- IMPORTANT: This migration requires that the organizations table exists.
-- It should be run AFTER migration 004_create_multi_tenant_tables.

-- Add organization_id to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS organization_id UUID;

-- Add foreign key constraint (must be done separately from ADD COLUMN IF NOT EXISTS)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'documents_organization_id_fkey'
        AND table_name = 'documents'
    ) THEN
        ALTER TABLE documents
        ADD CONSTRAINT documents_organization_id_fkey 
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_documents_organization_id ON documents(organization_id);

-- Add organization_id to chunks table  
ALTER TABLE chunks
ADD COLUMN IF NOT EXISTS organization_id UUID;

-- Add foreign key constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'chunks_organization_id_fkey'
        AND table_name = 'chunks'
    ) THEN
        ALTER TABLE chunks
        ADD CONSTRAINT chunks_organization_id_fkey 
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_chunks_organization_id ON chunks(organization_id);

-- Enable Row Level Security on documents table
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Create RLS policy for documents: users can only see documents from their organization
-- The policy allows access when:
-- 1. app.tenant_id is set and matches the row's organization_id, OR
-- 2. app.tenant_id is not set (for backward compatibility with non-tenant queries)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname = 'public' 
        AND tablename = 'documents' 
        AND policyname = 'documents_tenant_isolation'
    ) THEN
        CREATE POLICY documents_tenant_isolation ON documents
            FOR ALL
            USING (
                organization_id::text = current_setting('app.tenant_id', true)
                OR current_setting('app.tenant_id', true) IS NULL
                OR current_setting('app.tenant_id', true) = ''
            );
    END IF;
END $$;

-- Enable Row Level Security on chunks table
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

-- Create RLS policy for chunks: users can only see chunks from their organization
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname = 'public' 
        AND tablename = 'chunks' 
        AND policyname = 'chunks_tenant_isolation'
    ) THEN
        CREATE POLICY chunks_tenant_isolation ON chunks
            FOR ALL
            USING (
                organization_id::text = current_setting('app.tenant_id', true)
                OR current_setting('app.tenant_id', true) IS NULL
                OR current_setting('app.tenant_id', true) = ''
            );
    END IF;
END $$;

-- Note: The policies allow access when app.tenant_id is not set for backward compatibility.
-- In production, you should ensure app.tenant_id is always set via middleware.
-- Existing data will have NULL organization_id and will be visible to all users until
-- an organization is assigned. Admins should explicitly assign ownership of existing data.
