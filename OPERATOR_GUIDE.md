# Operator Guide

This guide documents day-2 operations for ingestion connectors and admin automation. For deployment prerequisites and release coordination refer to [DEPLOYMENT.md](DEPLOYMENT.md) and [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

> 🛠️ **Cobertura:** Procedimentos válidos para o release [v1.0.0](https://github.com/chatvolt/pdf-knowledge-kit/releases/tag/v1.0.0) (2025-11-15).

## Connector matrix

| Connector     | Endpoint                               | What it ingests                                                           | Required params                                                                                          | Credentials                                                                        | Notes                                                                     |
| ------------- | -------------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Database      | `POST /api/admin/ingest/database`      | Rows from PostgreSQL or any DSN accepted by `psycopg`.                    | `params.queries[]` (`sql`, `text_column`, `id_column`), optional `params.dsn` or `host`/`database` pair. | `credentials.values` may include `username`, `password`, or a full DSN.            | Use `connector_metadata` to label datasets (e.g., `{"team": "support"}`). |
| REST/API      | `POST /api/admin/ingest/api`           | JSON payloads from HTTP APIs.                                             | `params.endpoint` (or `base_url`), `params.text_fields`, `params.id_field`.                              | Store API keys/bearer tokens in `credentials.token` or header map.                 | Supports cursor/page pagination via `params.pagination`.                  |
| Transcription | `POST /api/admin/ingest/transcription` | Audio/video transcripts via `mock`, `whisper_local`, or `aws_transcribe`. | `params.provider`, `params.media_uri`; optional `params.cache_dir`, `params.language`.                   | Provide AWS credentials or Whisper configuration if not relying on local defaults. | Cache metadata stored under `tmp/transcriptions`.                         |

## Environment variables

Set these before calling admin endpoints:

- `ADMIN_API_KEY`, `OP_API_KEY`, `VIEW_API_KEY` – RBAC for viewers/operators/admins.
- `DATABASE_URL` – default Postgres connection for ingestion metadata.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` – required for AWS Transcribe.
- `ADMIN_UI_ORIGINS` – CORS allowlist when the admin UI is hosted elsewhere.
- Optional provider hints: `WHISPER_MODEL`, `WHISPER_COMPUTE_TYPE` for local Whisper, `PG*` variables for DSN-less DB connections.

## Credential handling

Secrets are stored verbatim in the database so operators should:

1. Resolve the secret value before sending it (no plain `{"secret_id": "..."}` references allowed).
2. Prefer fetching credentials from Vault/KMS/Secrets Manager in automation pipelines, then POSTing them inline.
3. Encrypt the Postgres volume at rest or fork `app/routers/admin_ingest_api.py` to add custom encryption if corporate policy requires it.
4. Rotate credentials by updating the connector definition (`PUT /api/admin/ingest/connector_definitions/{id}`) and re-running jobs.

## Automation workflow

Use `tools/register_connector.py` to register connectors and monitor jobs.

```bash
python tools/register_connector.py \
  --host https://kb.example.com \
  --operator-key "$OPERATOR_API_KEY" \
  --name marketing-rss \
  --api-endpoint /rss \
  --api-base https://status.example.com \
  --text-field summary --text-field updates.0.body
```

The script supports:

1. Creating or updating connector definitions.
2. Triggering ingestion jobs (`--run-now`).
3. Polling job status until completion while dumping `job_metadata` and `version` history snapshots.
4. Streaming incremental logs using the `--follow-logs` flag.

Review `python tools/register_connector.py --help` for the full CLI reference.

## Alert review checklists

Operators must validate alert hygiene before every release cut and whenever monitoring rules change. These checklists tie back to the triage flow described in [DEPLOYMENT.md](DEPLOYMENT.md#45-incident-triage-response-sla-and-escalation).

### Pre-release alert audit

- [ ] Confirm primary uptime, latency, and ingestion lag alerts cover the new endpoints or connectors being deployed.
- [ ] Review alert thresholds against the expected baseline gathered from staging load tests.
- [ ] Verify alert routing sends Sev1/Sev2 signals to the on-call rotation and mirrors notifications to `#pdfkit-ops`.
- [ ] Ensure dashboards or saved searches linked in alerts have up-to-date filters and time ranges.
- [ ] Record the audit outcome in the release issue following [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md#phase-1-pre-release-preparation).

### Post-incident follow-up

- [ ] Capture timeline, remediation, and detection gaps in the incident ticket.
- [ ] Adjust alert thresholds or suppression rules to avoid noise without masking real regressions.
- [ ] Link resulting action items to backlog tickets and confirm owners with the Platform Engineering lead.
- [ ] Share learnings in the next operations review and update this guide if new steps are standardized.

## Test data for new connectors

- Run `docker compose up -d db` to provision Postgres with pgvector.
- `pytest -k connector` exercises ingestion and transcription flows.
- For AWS Transcribe dry-runs, export fake credentials and point to `s3://` URIs backed by [LocalStack](https://github.com/localstack/localstack) or another mock service.
- When validating Whisper locally, install `faster-whisper` (GPU/CPU) or `openai-whisper` (PyTorch) and ensure FFmpeg is available in `PATH`.

## Sample payloads

```bash
# Database connector definition (operator role)
curl -X POST "$HOST/api/admin/ingest/connector_definitions" \
  -H "X-API-Key: $OPERATOR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-crm",
    "type": "database",
    "params": {
      "host": "db",
      "database": "crm",
      "queries": [{
        "name": "customers",
        "sql": "SELECT id, notes FROM customers",
        "text_column": "notes",
        "id_column": "id"
      }]
    },
    "credentials": {"values": {"username": "reader", "password": "s3cret"}}
  }'

# Trigger a job using a definition (database example)
curl -X POST "$HOST/api/admin/ingest/database" \
  -H "X-API-Key: $OPERATOR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"connector_definition_id": "<UUID>", "label": "crm"}'

# Fetch job metadata + sync history
curl -H "X-API-Key: $VIEW_API_KEY" \
  "$HOST/api/admin/ingest/jobs/<UUID>"
```

For log streaming, call `/api/admin/ingest/jobs/<UUID>/logs?offset=0` and increment the offset with the number of bytes already read.
