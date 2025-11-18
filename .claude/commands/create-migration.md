# Create Database Migration

Create a new database migration file following the project conventions.

## Steps

1. List existing migrations to determine the next number:
   - Check migrations/ directory
   - Find the highest numbered migration

2. Ask user for migration purpose/description

3. Create new migration file:
   - Format: `XXX_description.sql` (where XXX is next number with leading zeros)
   - Include header comment with description and date
   - Add transaction wrapper (BEGIN/COMMIT)
   - Include idempotency checks where applicable

4. Template structure:
   ```sql
   -- Migration XXX: [Description]
   -- Created: [Date]

   BEGIN;

   -- Your migration SQL here

   COMMIT;
   ```

5. Remind user to:
   - Test the migration
   - Add rollback script if needed
   - Update schema.sql if this is a structural change

Create the file and show the path where it was created.
