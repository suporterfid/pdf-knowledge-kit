import React, { useState } from 'react';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import useAuth from '../hooks/useAuth';

export default function IngestUrls() {
  const apiFetch = useAuthenticatedFetch();
  const { roles, tenantId } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [urls, setUrls] = useState<string[]>(['']);
  const [jobId, setJobId] = useState<string | null>(null);

  const handleChange = (idx: number, value: string) => {
    setUrls((prev) => prev.map((u, i) => (i === idx ? value : u)));
  };

  const addField = () => setUrls((prev) => [...prev, '']);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    interface StartJobResponse { job_id: string }
    const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
    apiFetch(`/api/admin/ingest/urls${tenantSuffix}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: urls.filter((u) => u) }),
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
      <h2>Multiple URL Ingestion</h2>
      <form onSubmit={submit} aria-label="URLs ingestion form">
        {urls.map((url, idx) => (
          <div key={idx}>
            <label htmlFor={`url-${idx}`}>URL {idx + 1}</label>
            <input
              id={`url-${idx}`}
              type="url"
              value={url}
              onChange={(e) => handleChange(idx, e.target.value)}
              required
            />
          </div>
        ))}
        <button type="button" onClick={addField} aria-label="Add another URL">Add URL</button>
        <button type="submit">Start</button>
      </form>
      {jobId && <p>Started job {jobId}</p>}
    </div>
  );
}
