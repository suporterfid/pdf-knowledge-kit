# Disaster Recovery Runbook

This runbook documents the end-to-end sequence for restoring the PDF Knowledge Kit
platform after a catastrophic failure affecting the managed PostgreSQL cluster or
application nodes. The objectives and timings assume production scale for release
[v1.0.0](https://github.com/chatvolt/pdf-knowledge-kit/releases/tag/v1.0.0) as of
2025-11-15.

## Recovery objectives

| Objective | Target | Owner |
| --- | --- | --- |
| Recovery Time Objective (RTO) | ≤ 60 minutes from incident declaration to service cutover | Platform Ops on-call |
| Recovery Point Objective (RPO) | ≤ 15 minutes of data loss using latest logical dump + WAL/snapshot | Database Reliability (DBRE) |
| Verification window | ≤ 15 minutes functional validation after restore | QA on-call |

## Prerequisites

1. Latest logical dump (`.dump`) exported with `pg_dump` and stored in the
   encrypted `s3://pdfkit-prod-backups` bucket.
2. Most recent volume snapshot identifier from the managed database service.
3. Access tokens for `platform-ops` IAM role with restore permissions.
4. Access to the staging VPC subnet (`10.16.0.0/16`) to perform dry-runs.
5. Current environment variables (`production.env`) stored in Vault.

## End-to-end restore procedure

The sequence below must be followed in order. Durations are cumulative estimates
for meeting the RTO and should be tracked in the incident timeline.

### 1. Declare incident and gather assets (5 minutes)

1. Incident commander (IC) opens a Sev1 ticket in Jira (`OPS-DR-<date>`) and posts
   in `#pdfkit-incident` with the summary, suspected impact, and decision to run a
   database restore.
2. DBRE on-call retrieves the latest logical dump path and the latest snapshot ID
   and shares them in the incident ticket.
3. Platform Ops on-call confirms who will act as IC, DBRE, QA, and communications
   lead.

### 2. Provision clean restore environment (10 minutes)

1. Launch a temporary restore host (t3.large or larger) in the `dr-restore`
   subnet using the Terraform module `infra/modules/restore_host`.
2. Attach a temporary volume with at least 2× the size of the database dump.
3. Install the PostgreSQL client tools:

   ```bash
   sudo apt-get update && sudo apt-get install -y postgresql-client-16 awscli
   ```

4. Download the dump from S3 and decrypt it:

   ```bash
   aws s3 cp s3://pdfkit-prod-backups/logical/pdfkit_latest.dump.gpg ./
   gpg --decrypt pdfkit_latest.dump.gpg > pdfkit_latest.dump
   ```

Expected duration: 10 minutes.

### 3. Restore logical backup to standby database (15 minutes)

1. Start a fresh managed Postgres instance or clone from the latest snapshot if
   point-in-time recovery (PITR) is required. For PITR, restore to `snapshot-<ts>`
   and apply WAL up to the requested timestamp.
2. Configure connectivity variables:

   ```bash
   export PGHOST=<standby-host>
   export PGPORT=5432
   export PGUSER=dr_restore
   export PGPASSWORD=$(vault kv get -field=password secret/platform/db/dr_restore)
   export PGDATABASE=pdfkit
   ```

3. Execute the restore:

   ```bash
   pg_restore \
     --verbose \
     --clean \
     --create \
     --jobs=8 \
     pdfkit_latest.dump
   ```

4. Monitor output for constraint or extension errors. If failures occur, rerun
   `pg_restore` with `--single-transaction` to isolate issues.

Expected duration: 15 minutes for a 50 GB logical dump using 8 jobs.

### 4. Post-restore maintenance (10 minutes)

1. Run index maintenance to rebuild any invalid or btree indexes:

   ```bash
   reindexdb --all --jobs=4
   ```

2. Refresh planner statistics:

   ```bash
   vacuumdb --analyze-in-stages --jobs=4 pdfkit
   ```

3. Verify integrity of vector indexes and critical tables:

   ```bash
   psql pdfkit <<'SQL'
   SELECT relname, pg_relation_size(relid) AS size_bytes
   FROM pg_stat_all_indexes
   WHERE schemaname = 'public'
     AND idx_scan = 0
   ORDER BY size_bytes DESC
   LIMIT 10;

   SELECT COUNT(*) FROM ingestion_jobs;
   SELECT COUNT(*) FROM conversation_messages;
   SQL
   ```

4. Confirm all required extensions are present:

   ```bash
   psql pdfkit -c "SELECT extname FROM pg_extension ORDER BY 1;"
   ```

Expected duration: 10 minutes.

### 5. Application cutover (10 minutes)

1. Update the connection string in Vault (`secret/platform/db/primary`) to point
   to the restored database endpoint.
2. Trigger a rolling restart of the backend using the deployment automation
   (`workflow_dispatch` → `production-redeploy`).
3. Validate that application pods establish connections to the new database and
   no errors appear in `kubectl logs`.
4. Notify stakeholders in `#pdfkit-status` that read/write traffic has been
   restored.

Expected duration: 10 minutes.

### 6. Functional verification (10 minutes)

QA on-call performs the following checks and records evidence in the incident
ticket:

- Execute smoke tests via `pytest -k smoke --base-url https://prod.pdfkit`.
- Validate semantic search against the staging dataset returns results within
  2 seconds P95.
- Confirm a new chat session can be created and messages persist.
- Review dashboards for ingestion lag and error rates returning to baseline.

Expected duration: 10 minutes.

## Post-incident follow-up

1. IC documents the timeline, decisions, and deviations in the incident ticket
   within 24 hours.
2. DBRE uploads restored database metrics (dump size, restore duration, WAL replay
   lag) to the operations tracker.
3. QA files any bugs discovered during verification into Jira with owners.
4. Update this runbook if additional steps were required.

## Validation cadence

- Perform a full dry-run using this runbook quarterly (aligned with the first
  business week of March, June, September, and December).
- Record evidence in `operations/dr-exercises/<year>-<quarter>.md` with start
  and end timestamps, owners, deviations, and remediation tasks.
- Failing to meet RTO/RPO triggers an immediate corrective action plan led by
  Platform Ops and DBRE leads.
