# Ingest Documents

Ingest documents into the knowledge base using the CLI or API.

## Steps

1. Check if documents exist in docs/ or sample_data/ directory
2. Use ingest.py CLI tool to ingest local documents:
   - Run: `python ingest.py --tenant-id <tenant_id>`
   - Show progress and results

3. Alternative: Use the admin API endpoint
   - POST to /api/admin/ingest/local
   - Include directory path and tenant information

4. Verify ingestion:
   - Check ingestion job status
   - Query for ingested chunks
   - Display statistics (documents, chunks, tokens)

Display a summary of what was ingested with document counts and any errors.
