-- Ensure tenant_id defaults from app.current_tenant_id() on inserts
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.ensure_tenant_id()
RETURNS trigger AS $$
BEGIN
  IF NEW.tenant_id IS NULL THEN
    NEW.tenant_id := app.current_tenant_id();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  rec RECORD;
BEGIN
  FOR rec IN
    SELECT unnest(ARRAY['documents','document_versions','chunks','sources','ingestion_jobs']) AS table_name
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS ensure_tenant_%I ON %I;', rec.table_name, rec.table_name);
    EXECUTE format(
      'CREATE TRIGGER ensure_tenant_%1$s BEFORE INSERT ON %1$s FOR EACH ROW EXECUTE PROCEDURE app.ensure_tenant_id();',
      rec.table_name
    );
  END LOOP;
END;
$$;
