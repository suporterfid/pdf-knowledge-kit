import React, { useState } from 'react';
import { useApiFetch } from '../apiKey';

export default function IngestUrls() {
  const apiFetch = useApiFetch();
  const [urls, setUrls] = useState<string[]>(['']);
  const [jobId, setJobId] = useState<string | null>(null);

  const handleChange = (idx: number, value: string) => {
    setUrls((prev) => prev.map((u, i) => (i === idx ? value : u)));
  };

  const addField = () => setUrls((prev) => [...prev, '']);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    apiFetch('/api/admin/ingest/jobs/urls', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(urls.filter((u) => u)),
    })
      .then((r) => r.json())
      .then((d) => setJobId(d.job_id))
      .catch(() => {});
  };

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
        <button type="button" onClick={addField}>Add URL</button>
        <button type="submit">Start</button>
      </form>
      {jobId && <p>Started job {jobId}</p>}
    </div>
  );
}
