import React, { useState } from 'react';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import useAuth from '../hooks/useAuth';

export default function IngestLocal() {
  const apiFetch = useAuthenticatedFetch();
  const { roles, tenantId } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [path, setPath] = useState('');
  const [useOcr, setUseOcr] = useState(false);
  const [lang, setLang] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);

  interface StartJobResponse { job_id: string }

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
    apiFetch(`/api/admin/ingest/local${tenantSuffix}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, use_ocr: useOcr, ocr_lang: lang || undefined }),
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
