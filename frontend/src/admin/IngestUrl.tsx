import React, { useState } from 'react';
import { useApiFetch } from '../apiKey';

export default function IngestUrl() {
  const apiFetch = useApiFetch();
  const [url, setUrl] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams({ url });
    apiFetch(`/api/admin/ingest/jobs/url?${params.toString()}`, { method: 'POST' })
      .then((r) => r.json())
      .then((d) => setJobId(d.job_id))
      .catch(() => {});
  };

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
