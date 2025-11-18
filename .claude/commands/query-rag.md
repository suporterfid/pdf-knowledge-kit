# Query the RAG System

Test semantic search queries against the knowledge base.

## Steps

1. Use query.py CLI tool to search:
   - Run: `python query.py "<search query>" --tenant-id <tenant_id>`
   - Show top results with relevance scores

2. Display results including:
   - Matched text chunks
   - Source documents
   - Similarity scores
   - Metadata

3. Optional: Compare with direct API call
   - POST to /api/ask with query
   - Show formatted response

Format the output in a readable way with clear separation between results.
