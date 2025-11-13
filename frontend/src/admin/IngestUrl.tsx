import React, { useState } from 'react';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import useAuth from '../hooks/useAuth';

export default function IngestUrl() {
  const apiFetch = useAuthenticatedFetch();
  const { roles, tenantId } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [url, setUrl] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);

  interface StartJobResponse { job_id: string }

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
    apiFetch(`/api/admin/ingest/url${tenantSuffix}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
      .then((r) => r.json() as Promise<StartJobResponse>)
      .then((d) => setJobId(d.job_id))
      .catch(() => {});
  };

  if (!canOperate) {
    return <p>You do not have permission to start ingestion.</p>;
  }

  return (
    <div>
      <h2>Single URL Ingestion</h2>
      <form onSubmit={submit} aria-label="URL ingestion form">
        <label htmlFor="url">URL</label>
        <input
          id="url"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
        <button type="submit">Start</button>
      </form>
      {jobId && <p>Started job {jobId}</p>}
    </div>
  );
}
