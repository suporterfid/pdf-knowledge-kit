import React, { useState } from 'react';
import { useApiFetch } from '../apiKey';

export default function IngestLocal() {
  const apiFetch = useApiFetch();
  const [path, setPath] = useState('');
  const [useOcr, setUseOcr] = useState(false);
  const [lang, setLang] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams({ path, use_ocr: String(useOcr) });
    if (lang) params.append('ocr_lang', lang);
    apiFetch(`/api/admin/ingest/jobs/local?${params.toString()}`, { method: 'POST' })
      .then((r) => r.json())
      .then((d) => setJobId(d.job_id))
      .catch(() => {});
  };

  return (
    <div>
      <h2>Local Folder Ingestion</h2>
      <form onSubmit={submit} aria-label="Local ingestion form">
        <label htmlFor="path">Path</label>
        <input id="path" value={path} onChange={(e) => setPath(e.target.value)} required />
        <label>
          <input
            type="checkbox"
            checked={useOcr}
            onChange={(e) => setUseOcr(e.target.checked)}
          />
          Use OCR
        </label>
        <label htmlFor="lang">OCR Language</label>
        <input id="lang" value={lang} onChange={(e) => setLang(e.target.value)} />
        <button type="submit">Start</button>
      </form>
      {jobId && <p>Started job {jobId}</p>}
    </div>
  );
}
